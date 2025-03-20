import os
import json
import firebase_admin
from firebase_admin import credentials, storage, firestore
from pathlib import Path
from typing import Optional, Dict, Any, Union
from datetime import timedelta
import tempfile
from retry_utils import retry_with_backoff

@retry_with_backoff(max_retries=3, initial_delay=1, exceptions_to_check=(Exception,))
def upload_file(file_path: Optional[str] = None, 
                destination_blob_name: str = None, 
                data: Optional[bytes] = None) -> Optional[str]:
    """
    Wrapper function to upload a file to Firebase Storage.
    
    Args:
        file_path: Local path to the file to upload (ignored if data is provided)
        destination_blob_name: Name for the file in Firebase Storage
        data: Binary data to upload (takes precedence over file_path if provided)
    
    Returns:
        str or None: A signed URL for the uploaded file, or None on failure
    """
    firebase_config = FirebaseConfig()
    return firebase_config.upload_file(file_path, destination_blob_name, data)

class FirebaseConfig:
    """Configuration and utility methods for Firebase integration."""
    
    def __init__(self):
        """Initialize Firebase configuration with credentials file."""
        # Set default paths
        self.FIREBASE_CREDENTIALS_PATH = os.environ.get(
            "FIREBASE_CREDENTIALS_PATH", 
            "firebase-credentials.json"
        )
        self.FIREBASE_BUCKET_NAME = os.environ.get(
            "FIREBASE_BUCKET_NAME", 
            "codetest-3203d.firebasestorage.app"
        )
        
        # Initialize Firebase if not already initialized
        self._initialize_firebase()
        self.db = firestore.client()
        self.bucket = storage.bucket()

    def _initialize_firebase(self) -> None:
        """Initialize Firebase if not already initialized."""
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(str(self.FIREBASE_CREDENTIALS_PATH))
                firebase_admin.initialize_app(cred, {
                    "storageBucket": self.FIREBASE_BUCKET_NAME
                })
        except Exception as e:
            print(f"Firebase initialization error: {e}")
            raise

    def upload_file(
        self,
        file_path: Optional[str] = None,
        destination_blob_name: str = None,
        data: Optional[bytes] = None
    ) -> Optional[str]:
        """
        Upload a file to Firebase Storage and return a signed URL valid for 1 hour.
        
        This method supports two modes:
          1. Upload from a local file: Provide a file_path and destination_blob_name.
          2. Upload from in-memory binary data: Provide the data and destination_blob_name.
        
        Parameters:
            file_path (str, optional): Local path to the file to upload. Ignored if 'data' is provided.
            destination_blob_name (str): The name for the file in Firebase Storage.
            data (bytes, optional): Binary data to upload. If provided, file_path is ignored.
        
        Returns:
            str or None: A signed URL for the uploaded file valid for 1 hour, or None on failure.
        """
        try:
            if not destination_blob_name:
                print("Destination blob name must be provided.")
                return None

            blob = self.bucket.blob(destination_blob_name)
            
            # If in-memory data is provided, upload that
            if data is not None:
                blob.upload_from_string(data)
                print(f"Uploaded in-memory data as {destination_blob_name}")
            # Otherwise, if a file path is provided, upload from file
            elif file_path is not None:
                blob.upload_from_filename(file_path)
                print(f"File {file_path} uploaded as {destination_blob_name}")
            else:
                print("Either file_path or data must be provided.")
                return None

            # Generate a signed URL that expires in 1 hour
            signed_url = blob.generate_signed_url(expiration=timedelta(hours=1))
            return signed_url
        
        except FileNotFoundError:
            print(f"File not found: {file_path}")
            return None
        except Exception as e:
            print(f"Upload error: {e}")
            return None

    def get_document(self, collection: str, doc_id: str) -> Optional[dict]:
        """Retrieve document from Firestore."""
        try:
            doc_ref = self.db.collection(collection).document(doc_id)
            doc = doc_ref.get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            print(f"Firestore error: {e}")
            return None

    def download_file_from_firebase(self, blob_name: str, local_filename: Optional[str] = None) -> Optional[Path]:
        """
        Download a file from Firebase Storage directly to the user's Downloads folder.
        
        Args:
            blob_name: The name of the file in Firebase Storage
            local_filename: Optional filename to use locally. If None, uses the blob name.
            
        Returns:
            Path: Path to the downloaded file in Downloads folder, or None if failed
        """
        try:
            from direct_download import get_downloads_folder
            
            # Get the Downloads folder
            downloads_folder = get_downloads_folder()
            if not downloads_folder.exists():
                downloads_folder.mkdir(parents=True, exist_ok=True)
            
            # Determine local filename
            if not local_filename:
                local_filename = os.path.basename(blob_name)
            
            # Create local file path
            local_path = downloads_folder / local_filename
            
            # Check for filename conflicts
            counter = 1
            original_stem = local_path.stem
            while local_path.exists():
                local_path = downloads_folder / f"{original_stem}_{counter}{local_path.suffix}"
                counter += 1
            
            # Get the blob
            blob = self.bucket.blob(blob_name)
            
            # Download the file
            print(f"Downloading {blob_name} from Firebase to {local_path}")
            blob.download_to_filename(str(local_path))
            
            if local_path.exists():
                print(f"File successfully downloaded to: {local_path}")
                return local_path
            else:
                print(f"Download failed: File not found at {local_path} after download")
                return None
                
        except Exception as e:
            print(f"Error downloading file from Firebase: {e}")
            return None


def download_file_to_downloads(blob_name: str, local_filename: Optional[str] = None) -> Optional[Path]:
    """
    Download a file from Firebase Storage directly to the user's Downloads folder.
    Standalone wrapper function.
    
    Args:
        blob_name: The name of the file in Firebase Storage
        local_filename: Optional filename to use locally. If None, uses the blob name.
        
    Returns:
        Path: Path to the downloaded file in Downloads folder, or None if failed
    """
    firebase_config = FirebaseConfig()
    return firebase_config.download_file_from_firebase(blob_name, local_filename)


def upload_json_to_firebase(json_data: Union[Dict, Any], destination_blob_name: str) -> Optional[str]:
    """
    Upload JSON data to Firebase Storage and return signed URL.
    
    Args:
        json_data: The JSON data to upload (dictionary or serializable object)
        destination_blob_name: The destination file name in Firebase Storage
        
    Returns:
        Optional[str]: The signed URL of the uploaded file or None if upload fails
    """
    try:
        # Create a temporary file to store the JSON
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            # Write JSON to the temporary file
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2)
        
        # Set up proper destination path
        destination_folder = "parsed_jsons"
        # If the destination_blob_name doesn't have .json extension, add it
        if not destination_blob_name.lower().endswith('.json'):
            destination_blob_name = f"{destination_blob_name}.json"
            
        # If it doesn't already start with the folder prefix, add it
        if not destination_blob_name.startswith(f"{destination_folder}/"):
            destination_blob_name = f"{destination_folder}/{destination_blob_name}"
        
        # Upload the temporary file to Firebase
        firebase_config = FirebaseConfig()
        signed_url = firebase_config.upload_file(tmp_path, destination_blob_name)
        
        # Clean up the temporary file
        os.unlink(tmp_path)
        
        if signed_url:
            print(f"JSON uploaded successfully to Firebase as {destination_blob_name}")
            print(f"Signed URL: {signed_url}")
            return signed_url
        return None
    except Exception as e:
        print(f"Error uploading JSON to Firebase: {e}")
        # Clean up the temporary file if it exists and there was an error
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return None

def download_file(blob_name: str) -> Optional[bytes]:
    """
    Download a file from Firebase Storage and return its contents as bytes.
    
    Args:
        blob_name: The name of the file in Firebase Storage
        
    Returns:
        Optional[bytes]: The file contents as bytes, or None if download fails
    """
    try:
        firebase_config = FirebaseConfig()
        
        # Check if blob exists with this name first
        blob = firebase_config.bucket.blob(blob_name)
        if not blob.exists():
            # Try with outputs/ prefix if not already there
            if not blob_name.startswith("outputs/"):
                alt_blob_name = f"outputs/{blob_name}"
                blob = firebase_config.bucket.blob(alt_blob_name)
                if blob.exists():
                    blob_name = alt_blob_name
                    blob = firebase_config.bucket.blob(blob_name)
                else:
                    print(f"File {blob_name} not found in Firebase Storage")
                    return None
            else:
                print(f"File {blob_name} not found in Firebase Storage")
                return None
            
        # Set correct content type for docx files
        if blob_name.lower().endswith('.docx'):
            blob.content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
        # Download the file to memory
        print(f"Downloading {blob_name} from Firebase")
        file_bytes = blob.download_as_bytes()
        
        print(f"Successfully downloaded {blob_name} ({len(file_bytes)} bytes)")
        return file_bytes
                
    except Exception as e:
        print(f"Error downloading file from Firebase: {e}")
        return None

if __name__ == "__main__":
    # Example usage
    test_file = "path/to/test.pdf"  # Make sure this file exists.
    result = upload_file(test_file, "test_upload.pdf")
    print(f"Upload result: {result}")
    
    # Example for JSON upload
    test_json = {"name": "Test User", "skills": ["Python", "Firebase"]}
    json_result = upload_json_to_firebase(test_json, "test_data.json")
    print(f"JSON upload result: {json_result}")
    
    # Example for downloading to Downloads folder
    download_path = download_file_to_downloads("test_upload.pdf")
    if download_path:
        print(f"Downloaded file to: {download_path}")