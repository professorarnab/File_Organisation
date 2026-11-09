import os
import sys
import shutil
from collections import defaultdict
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QFileDialog, QMessageBox, QCheckBox,
    QRadioButton, QButtonGroup, QTextEdit,
)
from PyQt6.QtCore import QThread, pyqtSignal


def get_month_year_dir(dt):
    """Convert a datetime to 'Jan25', 'Feb25' format"""
    return dt.strftime("%b%y")


class OrganizeWorker(QThread):
    """Background worker to prevent UI blocking"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(int, int, list)
    error = pyqtSignal(str)

    def __init__(self, main_dir, mode, overwrite, skip_existing):
        super().__init__()
        self.main_dir = main_dir
        self.mode = mode  # "extension" or "date"
        self.overwrite = overwrite
        self.skip_existing = skip_existing

    def run(self):
        try:
            groups = defaultdict(list)

            # 1. Scan and group files
            for entry in os.listdir(self.main_dir):
                full_path = os.path.join(self.main_dir, entry)
                if not os.path.isfile(full_path):
                    continue

                if self.mode == "date":
                    dt = datetime.fromtimestamp(os.path.getmtime(full_path))
                    key = get_month_year_dir(dt)
                else:  # extension
                    ext = os.path.splitext(entry)[1].lower()
                    key = ext if ext else "(no extension)"

                groups[key].append(full_path)

            total = sum(len(v) for v in groups.values())
            if total == 0:
                self.finished.emit(0, 0, [])
                return

            # 2. Emit initial status message
            status_msg = (
                f"Found {total} file(s). Organizing...\n\n" +
                "\n".join(f"{len(v)}x {k}" for k, v in groups.items())
            )
            self.status.emit(status_msg)

            moved_count = 0
            error_list = []
            processed = 0

            # 3. Move files to their respective folders
            for key, files in groups.items():
                target_dir = os.path.join(self.main_dir, key)
                os.makedirs(target_dir, exist_ok=True)
                
                for file_path in files:
                    dest_path = os.path.join(target_dir, os.path.basename(file_path))
                    
                    # Handle file conflicts based on user settings
                    if os.path.exists(dest_path):
                        if self.skip_existing:
                            processed += 1
                            self.progress.emit(int((processed / total) * 100))
                            continue
                        if not self.overwrite:
                            base, ext = os.path.splitext(dest_path)
                            counter = 1
                            while os.path.exists(dest_path):
                                dest_path = f"{base}_{counter}{ext}"
                                counter += 1

                    try:
                        shutil.move(file_path, dest_path)
                        moved_count += 1
                    except Exception as e:
                        error_list.append(f"{os.path.basename(file_path)}: {str(e)}")
                        
                    processed += 1
                    self.progress.emit(int((processed / total) * 100))

            # 4. Emit finished signal with summary
            self.finished.emit(total, moved_count, error_list)

        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Organizer")
        self.resize(550, 600)
        
        self.main_dir = ""
        self.worker = None

        # --- UI Setup ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Directory selection
        self.dir_label = QLabel("No directory selected.")
        self.select_dir_btn = QPushButton("Select Directory")
        self.select_dir_btn.clicked.connect(self.select_directory)
        
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.select_dir_btn)
        dir_layout.addWidget(self.dir_label, 1)
        layout.addLayout(dir_layout)

        # Mode selection (Radio buttons)
        mode_label = QLabel("Organize by:")
        self.mode_group = QButtonGroup()
        self.radio_ext = QRadioButton("Extension")
        self.radio_date = QRadioButton("Date (Month/Year)")
        self.radio_ext.setChecked(True)
        self.mode_group.addButton(self.radio_ext)
        self.mode_group.addButton(self.radio_date)
        
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.radio_ext)
        mode_layout.addWidget(self.radio_date)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Conflict Options (Checkboxes)
        self.chk_overwrite = QCheckBox("Overwrite existing files")
        self.chk_skip = QCheckBox("Skip existing files")
        
        opt_layout = QHBoxLayout()
        opt_layout.addWidget(self.chk_overwrite)
        opt_layout.addWidget(self.chk_skip)
        opt_layout.addStretch()
        layout.addLayout(opt_layout)

        # Start button
        self.start_btn = QPushButton("Start Organizing")
        self.start_btn.clicked.connect(self.start_organizing)
        layout.addWidget(self.start_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Status / Log area
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        layout.addWidget(self.status_text)

    def select_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            self.main_dir = dir_path
            self.dir_label.setText(os.path.basename(dir_path))
            self.status_text.clear()

    def start_organizing(self):
        if not self.main_dir:
            QMessageBox.warning(self, "Error", "Please select a directory first.")
            return
            
        mode = "date" if self.radio_date.isChecked() else "extension"
        overwrite = self.chk_overwrite.isChecked()
        skip = self.chk_skip.isChecked()

        # Lock UI and reset progress
        self.start_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_text.clear()

        # Start background thread
        self.worker = OrganizeWorker(self.main_dir, mode, overwrite, skip)
        self.worker.progress.connect(self.update_progress)
        self.worker.status.connect(self.update_status)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, msg):
        self.status_text.append(msg)

    def on_finished(self, total, moved, errors):
        self.start_btn.setEnabled(True)
        msg = f"\n\n--- Finished! ---\nTotal files: {total}\nMoved: {moved}"
        if errors:
            msg += f"\nErrors ({len(errors)}):\n" + "\n".join(errors)
        self.status_text.append(msg)
        QMessageBox.information(self, "Done", "File organization completed.")

    def on_error(self, error_msg):
        self.start_btn.setEnabled(True)
        self.status_text.append(f"\nCritical Error: {error_msg}")
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_msg}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
