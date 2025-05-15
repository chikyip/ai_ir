import os
import time
import threading
import re
from watchdog.events import FileSystemEventHandler
from image_analyzer import analyze_image_with_qwen

# Constants
MAX_EVENT_RATE = 10  # Max events per second per watcher
DEBOUNCE_DELAY = 2.0  # Seconds to wait after last event before processing

class ExtractHandler(FileSystemEventHandler):
    def __init__(self, request_semaphore):
        print("Initializing ExtractHandler for image processing")
        self.processing_images = set()
        self.lock = threading.Lock()
        self.pending_events = {}
        self.event_timestamps = []  # Track recent event times
        self.event_rate_semaphore = threading.Semaphore(MAX_EVENT_RATE)
        self.request_semaphore = request_semaphore

    def _throttle_events(self):
        """Ensure we don't process too many events too quickly"""
        now = time.time()
        # Remove old events (older than 1 second)
        self.event_timestamps = [t for t in self.event_timestamps if now - t < 1.0]
        
        if len(self.event_timestamps) >= MAX_EVENT_RATE:
            print(f"Throttling - too many events ({len(self.event_timestamps)} in last second)")
            time.sleep(0.1)  # Brief pause to slow down
            return False
        return True

    def on_created(self, event):
        print(f"Image file created event detected: {event.src_path}")
        self._schedule_image_event(event)
        
    def on_modified(self, event):
        print(f"Image file modified event detected: {event.src_path}")
        self._schedule_image_event(event)

    def _schedule_image_event(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            if not self._throttle_events():
                return
                
            # Cancel any pending processing for this file
            if event.src_path in self.pending_events:
                print(f"Cancelling previous pending processing for: {event.src_path}")
                self.pending_events[event.src_path].cancel()
                
            # Schedule new processing after 5 second delay
            timer = threading.Timer(5.0, self._process_image_event, [event])
            self.pending_events[event.src_path] = timer
            timer.start()
            print(f"Scheduled image processing for {event.src_path} in 5 seconds")
            
    def _process_image_event(self, event):
        # Clean up the pending event
        if event.src_path in self.pending_events:
            del self.pending_events[event.src_path]
            
        print(f"Processing image file: {event.src_path}")
        # Skip if file doesn't exist or is empty
        if not os.path.exists(event.src_path):
            print(f"Image file does not exist: {event.src_path}")
            return
        if os.path.getsize(event.src_path) == 0:
            print(f"Empty image file detected: {event.src_path}")
            return
            
        with self.lock:
            if event.src_path in self.processing_images:
                print(f"Image already being processed: {event.src_path}")
                return
                
            print(f"Lock acquired for image processing: {event.src_path}")
            self.processing_images.add(event.src_path)
            
        try:
            print(f"Extracting path info for: {event.src_path}")
            rel_path = os.path.relpath(event.src_path, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', 'extracts'))
            path_parts = rel_path.split(os.sep)
            
            # Update to handle new path structure: client/report_type/year/filename/image.jpg
            if len(path_parts) >= 4:  # Changed from 3 to 4
                client = path_parts[0]
                report_type = path_parts[1]
                year = path_parts[2]
                # filename = path_parts[3]  # Not needed in file_info
                
                # Validate year format
                if not year.isdigit():
                    print(f"Invalid year format in image path: {year}")
                    return
                    
                file_info = {
                    'filename': path_parts[3],
                    'path': event.src_path,
                    'client': client,
                    'report_type': report_type,
                    'year': year
                }
                
                print(f"Starting Qwen analysis for image: {event.src_path}")
                analyze_image_with_qwen(event.src_path, file_info, self.request_semaphore)
                print(f"Completed Qwen analysis for image: {event.src_path}")
                
            else:
                print(f"Unexpected path structure for image: {rel_path}")
                
        except Exception as e:
            print(f"Error processing image {event.src_path}: {str(e)}")
        finally:
            with self.lock:
                self.processing_images.remove(event.src_path)
                print(f"Processing complete and lock released for: {event.src_path}")
