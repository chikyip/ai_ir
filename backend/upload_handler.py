import os
import threading
import time  # Add this import
from watchdog.events import FileSystemEventHandler
from pdf_processor import process_pdf_with_qwen

class UploadHandler(FileSystemEventHandler):
    def __init__(self, upload_folder):
        print("Initializing UploadHandler")
        self.processing_files = set()
        self.pending_events = {}
        self.upload_folder = upload_folder
        self.lock = threading.Lock()  # Add thread lock

    # Add these event handler methods
    def on_created(self, event):
        self._schedule_pdf_event(event)
        
    def on_modified(self, event):
        self._schedule_pdf_event(event)

    def _schedule_pdf_event(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            # Skip if file doesn't exist or is empty
            if not os.path.exists(event.src_path) or os.path.getsize(event.src_path) == 0:
                print(f"Skipping empty/nonexistent file: {event.src_path}")
                return
                
            with self.lock:  # Add thread safety
                # Cancel any previous pending processing for this file
                if event.src_path in self.pending_events:
                    print(f"Cancelling previous pending processing for: {event.src_path}")
                    self.pending_events[event.src_path].cancel()
                    
                # Schedule new processing after 5 second delay
                timer = threading.Timer(5.0, self._process_pdf_event, [event])
                self.pending_events[event.src_path] = timer
                timer.start()
                print(f"Scheduled processing for {event.src_path} in 5 seconds")

    def _process_pdf_event(self, event):
        # Clean up pending event
        with self.lock:  # Add thread safety
            if event.src_path in self.pending_events:
                del self.pending_events[event.src_path]
                
        print(f"Processing PDF file: {event.src_path}")
        self.processing_files.add(event.src_path)
        try:
            print(f"Starting processing: {event.src_path}")
            # Get relative path from UPLOAD_FOLDER
            rel_path = os.path.relpath(event.src_path, self.upload_folder)
            path_parts = rel_path.split(os.sep)
            
            try:
                # Expected path structure: client/report_type/year/filename.pdf
                if len(path_parts) >= 3:
                    client = path_parts[0]
                    report_type = path_parts[1]
                    year = path_parts[2]
                    filename = path_parts[-1]
                    
                    # Validate year is numeric (or adjust as needed)
                    if not year.isdigit():
                        print(f"Invalid year format: {year}")
                        return
                else:
                    print(f"Unexpected path structure: {rel_path}")
                    return
                
                file_info = {
                    'filename': filename,
                    'path': event.src_path,
                    'client': client,
                    'report_type': report_type,
                    'year': year
                }
                
                # Process the PDF and analyze with Qwen
                process_pdf_with_qwen(file_info)
            except Exception as e:
                print(f"Error processing PDF: {str(e)}")
        finally:
            self.processing_files.remove(event.src_path)
            self.recently_processed[event.src_path] = time.time()  # Mark as processed
            print(f"Completed processing for: {event.src_path}")