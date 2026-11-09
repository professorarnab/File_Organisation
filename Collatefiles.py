import os
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QProgressBar, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog,
)
from PyQt6.QtCore import Qt


class FileCopier(QMainWindow):
    """GUI application to copy all files from subdirectories into a main directory."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Subdirectory File Copier")
        self.resize(500, 200)

        # State variables
        self.main_dir = None
        self.copied_count = 0
        self.total_files = 0

        self._build_ui()

    def _build_ui(self):
        """Build the main window UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Label showing current selection status
        self.status_label = QLabel("No directory selected")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.status_label)

        # Progress bar for copy operation feedback
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate until total is known
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Buttons row
        button_row = QHBoxLayout()

        select_button = QPushButton("Choose Main Directory")
        select_button.clicked.connect(self.choose_directory)
        button_row.addWidget(select_button)

        copy_button = QPushButton("Copy Files")
        copy_button.clicked.connect(self.copy_files)
        button_row.addWidget(copy_button)

        # Exit button to close the application
        exit_button = QPushButton("Exit")
        exit_button.clicked.connect(self.close_application)
        button_row.addWidget(exit_button)

        layout.addLayout(button_row)

    def choose_directory(self):
        """Open a dialog to let the user pick the main directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Main Directory", ""
        )
        if directory:
            self.main_dir = Path(directory)
            self.status_label.setText(
                f"Selected: {self.main_dir}\n"
                f"Files with the same name will be saved with a suffix (e.g., photo_01.jpg)."
            )

    def close_application(self):
        """Close the application."""
        reply = QMessageBox.question(
            self, "Exit", "Are you sure you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close()

    def _iter_subdirectory_files(self):
        """Yield absolute paths of every regular file inside subdirectories."""
        for root, _, files in os.walk(self.main_dir):
            for name in files:
                full_path = Path(root) / name
                # Skip files located directly in the main directory itself
                if full_path.parent == self.main_dir:
                    continue
                yield full_path

    def _get_unique_destination(self, source_path):
        """Return a path inside main_dir that does not already exist. If a file with the same name exists, insert a zero-padded number (01, 02, ...) before the extension: photo.jpg -> photo_01.jpg."""
        dest = self.main_dir / source_path.name
        if not dest.exists():
            return dest

        # Split into stem and suffix so the number goes before the extension.
        name = source_path.name
        stem, ext = Path(name).stem, Path(name).suffix
        counter = 1
        while True:
            candidate = dest.with_name(f"{stem}_{counter:02d}{ext}")
            if not candidate.exists():
                return candidate
            counter += 1

    def copy_files(self):
        """Copy all files from subdirectories into the main directory."""
        if not self.main_dir:
            QMessageBox.warning(
                self, "No Directory", "Please choose a main directory first."
            )
            return

        if not self.main_dir.is_dir():
            QMessageBox.critical(self, "Invalid Path", f"{self.main_dir} is not a valid directory.")
            return

        # Count total files to be copied
        self.total_files = sum(1 for _ in self._iter_subdirectory_files())
        if self.total_files == 0:
            QMessageBox.information(self, "Nothing to Do", "No subdirectory files found.")
            return

        # Setup progress bar
        self.progress_bar.setMaximum(self.total_files)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        copied = []
        current_count = 0
        conflict_count = 0
        for file_path in self._iter_subdirectory_files():
            try:
                # Generate a destination that won't overwrite an existing file
                dest = self._get_unique_destination(file_path)
                shutil.copy2(file_path, dest)
                copied.append(str(dest))
                if dest.name != file_path.name:
                    conflict_count += 1
            except Exception as error:
                print(f"Failed to copy {file_path}: {error}")

            # Update progress bar and UI
            current_count += 1
            self.progress_bar.setValue(current_count)
            QApplication.processEvents()  # Keeps UI responsive during the loop

        # Update UI after copying completes
        self.copied_count = len(copied)

        if conflict_count:
            QMessageBox.information(
                self, "Done", f"Successfully copied {self.copied_count} file(s).\n"
                f"{conflict_count} had name conflicts and were renamed."
            )
        else:
            QMessageBox.information(self, "Done", f"Successfully copied {self.copied_count} file(s).")


# Notice that `main()` is now unindented and sits outside the class
def main():
    app = QApplication([])
    window = FileCopier()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
