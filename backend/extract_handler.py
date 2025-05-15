import os
import time
import threading
import re
import subprocess
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
        self.pdf_tracking = {}  # Track PDF processing status

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
                pdf_name = path_parts[3]
                
                # Validate year format
                if not year.isdigit():
                    print(f"Invalid year format in image path: {year}")
                    return
                    
                file_info = {
                    'filename': pdf_name,
                    'path': event.src_path,
                    'client': client,
                    'report_type': report_type,
                    'year': year
                }
                
                print(f"Starting Qwen analysis for image: {event.src_path}")
                analyze_image_with_qwen(event.src_path, file_info, self.request_semaphore)
                print(f"Completed Qwen analysis for image: {event.src_path}")
                
                # Schedule a check to see if all pages are processed
                self._schedule_completion_check(client, report_type, year, pdf_name)
                
            else:
                print(f"Unexpected path structure for image: {rel_path}")
                
        except Exception as e:
            print(f"Error processing image {event.src_path}: {str(e)}")
        finally:
            with self.lock:
                self.processing_images.remove(event.src_path)
                print(f"Processing complete and lock released for: {event.src_path}")
    
    def _schedule_completion_check(self, client, report_type, year, pdf_name):
        """Schedule a check to see if all pages have been processed"""
        pdf_key = f"{client}/{report_type}/{year}/{pdf_name}"
        
        # Cancel any existing timer for this PDF
        if pdf_key in self.pdf_tracking:
            self.pdf_tracking[pdf_key].cancel()
        
        # Create a new timer to check completion
        timer = threading.Timer(30.0, self._check_processing_complete, 
                               [client, report_type, year, pdf_name])
        timer.daemon = True
        self.pdf_tracking[pdf_key] = timer
        timer.start()
        print(f"Scheduled completion check for {pdf_key} in 30 seconds")
    
    def _check_processing_complete(self, client, report_type, year, pdf_name):
        """Check if all pages have been processed and run category processing if so"""
        try:
            pdf_key = f"{client}/{report_type}/{year}/{pdf_name}"
            print(f"Checking if processing is complete for {pdf_key}")
            
            # Count images in extracts directory
            extracts_dir = os.path.join(
                os.path.dirname(__file__),
                'extracts',
                client,
                report_type,
                year,
                pdf_name
            )
            
            # Count JSON files in jsons directory
            jsons_dir = os.path.join(
                os.path.dirname(__file__),
                'jsons',
                client,
                report_type,
                year,
                pdf_name
            )
            
            if not os.path.exists(extracts_dir):
                print(f"Extracts directory not found for {pdf_key}")
                return
                
            # Count image files
            image_count = sum(1 for root, dirs, files in os.walk(extracts_dir) 
                             for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png')))
            
            # Count JSON files
            json_count = 0
            if os.path.exists(jsons_dir):
                json_count = sum(1 for root, dirs, files in os.walk(jsons_dir) 
                                for f in files if f.endswith('.json'))
            
            print(f"Found {image_count} images and {json_count} JSON files for {pdf_key}")
            
            # If all images have corresponding JSON files, process categories
            if image_count > 0 and json_count >= image_count:
                print(f"All pages processed for {pdf_key}, running category processing")
                self._process_categories(client, report_type, year, pdf_name)
            else:
                # Schedule another check if not complete
                print(f"Processing not complete for {pdf_key} ({json_count}/{image_count}), scheduling another check")
                timer = threading.Timer(30.0, self._check_processing_complete, 
                                       [client, report_type, year, pdf_name])
                timer.daemon = True
                self.pdf_tracking[pdf_key] = timer
                timer.start()
        except Exception as e:
            print(f"Error checking processing completion: {str(e)}")
    
    def _process_categories(self, client, report_type, year, pdf_name):
        """Run the process_categories.py script for the completed PDF"""
        try:
            print(f"Starting category processing for {client}/{report_type}/{year}/{pdf_name}")
            
            # Construct the command to run process_categories.py
            cmd = [
                "python3",
                os.path.join(os.path.dirname(__file__), "process_categories.py"),
                client,
                report_type,
                year,
                pdf_name
            ]
            
            # Run the process with proper output handling
            process = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(__file__),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Create threads to read output (prevents hanging)
            def read_output(pipe, prefix):
                for line in iter(pipe.readline, ''):
                    if line:
                        print(f"{prefix}: {line.strip()}")
                
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, "CATEGORY_STDOUT"))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, "CATEGORY_STDERR"))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            print(f"Category processing initiated for {client}/{report_type}/{year}/{pdf_name}")
            
            # Remove from tracking
            pdf_key = f"{client}/{report_type}/{year}/{pdf_name}"
            if pdf_key in self.pdf_tracking:
                del self.pdf_tracking[pdf_key]
                
        except Exception as e:
            print(f"Error starting category processing: {str(e)}")

    # Add this method to the ExtractHandler class
    def process_existing_pdfs(self):
        """Process categories for PDFs that have already been analyzed"""
        try:
            print("Checking for already processed PDFs that need category processing")
            extracts_dir = os.path.join(os.path.dirname(__file__), 'extracts')
            jsons_dir = os.path.join(os.path.dirname(__file__), 'jsons')
            
            # Walk through the extracts directory to find all PDFs
            for client in os.listdir(extracts_dir):
                client_path = os.path.join(extracts_dir, client)
                if not os.path.isdir(client_path):
                    continue
                    
                for report_type in os.listdir(client_path):
                    report_path = os.path.join(client_path, report_type)
                    if not os.path.isdir(report_path):
                        continue
                        
                    for year in os.listdir(report_path):
                        year_path = os.path.join(report_path, year)
                        if not os.path.isdir(year_path) or not year.isdigit():
                            continue
                            
                        for pdf_name in os.listdir(year_path):
                            pdf_path = os.path.join(year_path, pdf_name)
                            if not os.path.isdir(pdf_path):
                                continue
                                
                            # Check if this PDF has already been analyzed
                            pdf_key = f"{client}/{report_type}/{year}/{pdf_name}"
                            
                            # Skip if already being tracked
                            if hasattr(self, 'pdf_tracking') and pdf_key in self.pdf_tracking:
                                continue
                                
                            # Schedule a completion check for this PDF
                            print(f"Scheduling check for existing PDF: {pdf_key}")
                            self._schedule_completion_check(client, report_type, year, pdf_name)
                            
            print("Finished scheduling checks for existing PDFs")
        except Exception as e:
            print(f"Error processing existing PDFs: {str(e)}")
