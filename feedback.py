from typing import Dict, Any, Optional, List
from enum import Enum
import time
from dataclasses import dataclass
from datetime import datetime

class FeedbackType(Enum):
    """Types of feedback messages"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PROGRESS = "progress"

@dataclass
class ProcessingStage:
    """Represents a stage in the CV processing pipeline"""
    name: str
    description: str
    estimated_time: int  # in seconds
    order: int

class ProcessingStatus:
    """Tracks the status of CV processing"""
    STAGES = {
        'upload': ProcessingStage('Upload', 'Uploading and validating CV', 5, 1),
        'parse': ProcessingStage('Parse', 'Extracting information from CV', 15, 2),
        'blurb': ProcessingStage('Blurb', 'Generating career summary', 20, 3),
        'location': ProcessingStage('Location', 'Classifying work locations', 5, 4),
        'enrich': ProcessingStage('Enrich', 'Enriching CV data', 10, 5),
        'generate': ProcessingStage('Generate', 'Generating final document', 10, 6),
    }

    def __init__(self):
        self.current_stage = None
        self.start_time = None
        self.stage_progress = {}
        self.messages = []

    def start_stage(self, stage_name: str):
        """Start tracking a new processing stage"""
        if stage_name in self.STAGES:
            self.current_stage = stage_name
            self.start_time = time.time()
            self.stage_progress[stage_name] = {
                'status': 'in_progress',
                'start_time': self.start_time,
                'completion_time': None
            }

    def complete_stage(self, stage_name: str, success: bool = True):
        """Mark a stage as completed"""
        if stage_name in self.stage_progress:
            self.stage_progress[stage_name].update({
                'status': 'completed' if success else 'failed',
                'completion_time': time.time()
            })

    def get_progress(self) -> Dict[str, Any]:
        """Get the current processing progress"""
        total_stages = len(self.STAGES)
        completed_stages = sum(1 for stage in self.stage_progress.values() 
                             if stage['status'] == 'completed')
        
        current_stage_info = self.STAGES.get(self.current_stage, None)
        
        return {
            'total_stages': total_stages,
            'completed_stages': completed_stages,
            'progress_percentage': (completed_stages / total_stages) * 100,
            'current_stage': {
                'name': current_stage_info.name if current_stage_info else None,
                'description': current_stage_info.description if current_stage_info else None,
                'estimated_time': current_stage_info.estimated_time if current_stage_info else None
            } if self.current_stage else None,
            'stage_details': self.stage_progress
        }

class FeedbackManager:
    """Manages user feedback and progress updates"""
    
    def __init__(self):
        self.processing_status = ProcessingStatus()
        self.messages = []
        self._max_messages = 100  # Prevent memory issues with too many messages

    def add_message(self, message: str, msg_type: FeedbackType, details: Optional[Dict] = None):
        """Add a new feedback message"""
        timestamp = datetime.now().isoformat()
        
        message_data = {
            'timestamp': timestamp,
            'type': msg_type.value,
            'message': message,
            'details': details or {}
        }
        
        self.messages.append(message_data)
        
        # Maintain message limit
        if len(self.messages) > self._max_messages:
            self.messages = self.messages[-self._max_messages:]
        
        return message_data

    def start_processing(self, filename: str):
        """Initialize processing tracking for a new file"""
        self.processing_status = ProcessingStatus()
        self.add_message(
            f"Starting CV processing for: {filename}",
            FeedbackType.INFO,
            {'filename': filename}
        )

    def update_progress(self, stage: str, status: str, message: str):
        """Update processing progress"""
        if stage in ProcessingStatus.STAGES:
            if status == 'start':
                self.processing_status.start_stage(stage)
                self.add_message(
                    f"Starting {ProcessingStatus.STAGES[stage].name}: {message}",
                    FeedbackType.INFO,
                    {'stage': stage, 'status': status}
                )
            elif status == 'complete':
                self.processing_status.complete_stage(stage, True)
                self.add_message(
                    f"Completed {ProcessingStatus.STAGES[stage].name}: {message}",
                    FeedbackType.SUCCESS,
                    {'stage': stage, 'status': status}
                )
            elif status == 'error':
                self.processing_status.complete_stage(stage, False)
                self.add_message(
                    f"Error in {ProcessingStatus.STAGES[stage].name}: {message}",
                    FeedbackType.ERROR,
                    {'stage': stage, 'status': status}
                )

    def get_status(self) -> Dict[str, Any]:
        """Get current processing status and messages"""
        return {
            'progress': self.processing_status.get_progress(),
            'messages': self.messages[-10:],  # Return last 10 messages
            'has_error': any(msg['type'] == 'error' for msg in self.messages)
        }

    def format_error(self, error: Exception, stage: str) -> Dict[str, Any]:
        """Format error information for user feedback"""
        error_type = type(error).__name__
        error_msg = str(error)
        
        # Map common errors to user-friendly messages
        user_messages = {
            'FileNotFoundError': 'The file could not be found. Please try uploading again.',
            'ValidationError': 'The CV data is invalid or incomplete.',
            'SecurityError': 'A security check failed. Please ensure your file is safe.',
            'JSONDecodeError': 'The CV data is not in the correct format.',
            'PermissionError': 'The system does not have permission to access the file.'
        }
        
        user_message = user_messages.get(error_type, 'An unexpected error occurred.')
        
        return {
            'error_type': error_type,
            'stage': stage,
            'message': user_message,
            'details': error_msg,
            'timestamp': datetime.now().isoformat()
        }

# Global feedback manager instance
feedback_manager = FeedbackManager() 