import os
import shutil
from collections import defaultdict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QFileDialog, QMessageBox, QCheckBox,
)
from PyQt6.QtCore import QThread, pyqtSignal


class OrganizeWorker(QThread):
    """Background worker to prevent UI blocking"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(int, int, list)
    error = pyqtSignal(str)

    def __init__(self, main_dir, overwrite, skip_existing):
        super().__init__()
        self.main_dir = main_dir
        self.overwrite = overwrite
        self.skip_existing = skip_existing

    def run(self):
        try:
            # Group files by extension
            groups = defaultdict(list)
            for entry in os.listdir(self.main_dir):
                full_path = os.path.join(self.main_dir, entry)
                if os.path.isfile(full_path):
                    ext = os.path.splitext(entry)[1]
                    key = ext if ext else "(no extension)"
                    groups[key].append(full_path)

            total = sum(len(v) for v in groups.values())
            status_msg = (
                f"Found {total} file(s). Organizing...\n\n" +
                "\n".join(f"{len(v)}x {ext}" for ext, v in sorted(groups.items()))
            )
            self.status.emit(status_msg)

            # Copy and delete files
            count = 0
            skipped = 0
            errors = []

            for key, files in groups.items():
                target_dir = os.path.join(self.main_dir, key)
                if self.skip_existing and os.path.isdir(target_dir):
                    continue
                os.makedirs(target_dir, exist_ok=True)

                for src in files:
                    filename = os.path.basename(src)
                    dest = os.path.join(target_dir, filename)

                    if os.path.exists(dest):
                        if self.overwrite:
                            try:
                                shutil.copy2(src, dest)
                                # Verify copy succeeded before deleting source
                                if os.path.exists(dest):
                                    os.remove(src)
                                count += 1
                            except Exception as e:
                                errors.append(f"Error processing {filename}: {e}")
                        else:
                            skipped += 1
                            continue
                    else:
                        try:
                            shutil.copy2(src, dest)
                            # Verify copy succeeded before deleting source
                            if os.path.exists(dest):
                                os.remove(src)
                            count += 1
                        except Exception as e:
                            errors.append(f"Error processing {filename}: {e}")

                    if total > 0:
                        self.progress.emit(int((count / total) * 100))

            self.finished.emit(count, skipped, errors)

        except Exception as e:
            self.error.emit(str(e))


class FileOrganizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Organizer")
        self.resize(540, 260)
        self.main_dir = ""
        self.worker = None

        # Central widget + vertical layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)

        # Title
        title = QLabel("File Organizer")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Choose directory button
        select_btn = QPushButton("Choose Directory")
        select_btn.clicked.connect(self.select_directory)
        layout.addWidget(select_btn)

        # Status label
        self.status_label = QLabel("Select a directory to organize files.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Options row
        options_row = QHBoxLayout()
        self.overwrite_check = QCheckBox("Overwrite existing files")
        self.skip_existing_dir_check = QCheckBox("Skip if subdirectory exists")
        options_row.addWidget(self.overwrite_check)
        options_row.addWidget(self.skip_existing_dir_check)
        layout.addLayout(options_row)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Organize button
        self.organize_btn = QPushButton("Organize Files")
        self.organize_btn.clicked.connect(self.organize_files)
        layout.addWidget(self.organize_btn)

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select the main directory")
        if directory:
            self.main_dir = directory
            self.status_label.setText(f"Selected directory:\n{directory}")

    def organize_files(self):
        if not self.main_dir:
            QMessageBox.warning(self, "No Directory", "Please choose a directory first.")
            return

        # Disable button and show progress
        self.organize_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        # Run file operations in background thread
        self.worker = OrganizeWorker(
            self.main_dir,
            self.overwrite_check.isChecked(),
            self.skip_existing_dir_check.isChecked()
        )
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status.connect(self.status_label.setText)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_finished(self, count, skipped, errors):
        summary = f"Done. Moved {count} file(s), skipped {skipped}."
        if errors:
            summary += f"\n{len(errors)} error(s) occurred."
        self.status_label.setText(summary)
        QMessageBox.information(self, "Complete", summary)
        self.organize_btn.setEnabled(True)
        self.progress.setVisible(False)

    def on_error(self, error_msg):
        self.status_label.setText(f"Error: {error_msg}")
        QMessageBox.critical(self, "Error", error_msg)
        self.organize_btn.setEnabled(True)
        self.progress.setVisible(False)


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = FileOrganizer()
    window.show()
    sys.exit(app.exec())
