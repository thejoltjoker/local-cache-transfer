#!/usr/bin/env python3
"""script_name.py
Description of script_name.py.
"""
import json
import logging
import shutil
import tempfile

from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, \
    QListWidget, QLabel
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from pathlib import Path
import time
import sys


def format_seconds(seconds):
    """
    Formats a given number of seconds into the HH:MM:SS time format.

    Args:
        seconds (int): Number of seconds to be formatted.

    Returns:
        str: Formatted time string in HH:MM:SS format.
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    time_format = f"{hours:02}:{minutes:02}:{seconds:02}"
    return time_format


def read_temp_file(name='local_cache_tool.json'):
    """
    Reads data from a temporary JSON file.

    Args:
        name (str, optional): Name of the temporary JSON file. Defaults to 'local_cache_tool.json'.

    Returns:
        dict: Loaded JSON data from the temporary file, or an empty dictionary if the file doesn't exist.
    """
    temp_file = Path(tempfile.gettempdir()) / name
    if temp_file.is_file():
        with temp_file.open('r') as read_file:
            return json.load(read_file) or {}
    return {}


def write_temp_file(data, name='local_cache_tool.json'):
    """
    Writes data to a temporary JSON file.

    Args:
        data (dict): Data to be written to the JSON file.
        name (str, optional): Name of the temporary JSON file. Defaults to 'local_cache_tool.json'.
    """
    temp_file = Path(tempfile.gettempdir()) / name
    with temp_file.open('w') as write_file:
        return json.dump(data, write_file) or {}


def get_total_files(paths: list[Path]):
    """
    Get the total file count in a list of paths

    Args:
        paths (list): list of Path objects

    Returns:
        int: total file count
    """
    files = 0
    for path in paths:
        files += len([x for x in path.rglob('*.*')])
    return files


class CopyThread(QThread):
    progress_update = pyqtSignal(int)

    def __init__(self, source_paths: list, source_root: Path, destination_root: Path):
        super().__init__()
        self.source_paths = source_paths
        self.source_root = source_root
        self.destination_root = destination_root
        self.start_time = time.time()

    def run(self):
        total_files = get_total_files(self.source_paths)
        copied_files = 0.0001
        transfer_percentage = copied_files / total_files
        # Reset timer
        self.start_time = time.time()

        for source in self.source_paths:
            logging.info(f'Processing {source}')
            source = Path(source)
            # self.progress_update.emit(transfer_percentage)

            # Create parent folder
            destination = self.destination_root / source.relative_to(self.source_root)
            logging.info(f'Creating destination folder {destination}')
            destination.mkdir(parents=True, exist_ok=True)

            # Get files to copy in alphabetical order
            files = sorted([x for x in source.rglob('*.*')])
            logging.info(f'{len(files)} files found in {source}')
            # Timer
            # total_size = sum([x.stat().st_size for x in files])
            # transferred_size = 1
            # transfer_percentage = transferred_size / total_size
            current_time = time.time()

            for i, f in enumerate(files, 1):
                # Destination path
                d = self.destination_root / f.relative_to(self.source_root)

                # Time estimation
                time_spent = current_time - self.start_time
                total_estimated_time = time_spent / transfer_percentage
                time_left = total_estimated_time - time_spent

                logging.info(
                    f'[{i}/{len(files)} | {round(transfer_percentage)}% | {format_seconds(int(time_left))}] {f} -> {d}')

                # Copy file
                shutil.copy2(f, d)
                # Add file size to transferred size
                # transferred_size += f.stat().st_size

                # Update variables for estimation
                transfer_percentage = (copied_files / total_files) * 100
                # transfer_percentage = transferred_size / total_size
                current_time = time.time()
                copied_files += 1

            # Rename original to show that it's using local files
            source.rename(source.parent / f'_{source.name}')

        self.progress_update.emit(100)  # Signal completion


class CalculateSizeThread(QThread):
    size_calculated = pyqtSignal(int)

    def __init__(self, source_path):
        super().__init__()
        self.source_path = source_path

    def run(self):
        total_size = 0

        for file_path in self.source_path.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        self.size_calculated.emit(total_size)


def format_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    size_names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(size_bytes // 1024 ** (i := min(int(size_bytes).bit_length() // 10, 8)))
    return f"{i:.1f} {size_names[i]}"


class MainWidget(QMainWindow):
    def __init__(self):
        super().__init__()
        self.total_size = 1
        self.setWindowTitle("Localize renders")
        self.resize(720, 480)
        self.setAcceptDrops(True)

        self.initUI()

    def initUI(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        # Listbox for dragged and dropped paths
        self.list_widget = DragDropListWidget()

        # Line edits for source and destination paths
        temp_file_content = read_temp_file()
        self.source_edit = QLineEdit(temp_file_content.get('source_root', 'L:\\'))
        self.source_edit.textChanged.connect(self.save_roots_to_temp_file)
        self.destination_edit = QLineEdit(temp_file_content.get('destination_root', 'D:\\'))
        self.destination_edit.textChanged.connect(self.save_roots_to_temp_file)

        # Push button
        self.start_button = QPushButton("Start")

        # Label for total size
        self.size_label = QLabel("Status: Drag and drop source folders into the list")

        # Layouts
        main_layout = QVBoxLayout()
        path_layout = QHBoxLayout()

        main_layout.addWidget(self.list_widget)
        path_layout.addWidget(QLabel('Source root:'))
        path_layout.addWidget(self.source_edit)
        path_layout.addWidget(QLabel('Destination root:'))
        path_layout.addWidget(self.destination_edit)
        path_layout.addWidget(self.start_button)

        main_layout.addLayout(path_layout)
        main_layout.addWidget(self.size_label)

        central_widget.setLayout(main_layout)

        self.start_button.clicked.connect(self.start_threads)

    def save_roots_to_temp_file(self):
        data = {'source_root': self.source_edit.text(),
                'destination_root': self.destination_edit.text()}
        write_temp_file(data)

    def start_threads(self):
        source_paths = [Path(self.list_widget.item(i).text()) for i in range(self.list_widget.count())]
        logging.debug(source_paths)
        source_root = Path(self.source_edit.text())
        destination_root = Path(self.destination_edit.text())

        self.copy_thread = CopyThread(source_paths, source_root, destination_root)
        self.copy_thread.progress_update.connect(self.update_progress)
        self.copy_thread.start()

        # self.calculate_size_thread = CalculateSizeThread(source_path)
        # self.calculate_size_thread.size_calculated.connect(self.update_size_label)
        # self.calculate_size_thread.start()

    def update_progress(self, progress_percentage):
        self.size_label.setText(f"Status: Copying... {progress_percentage}%")

    def update_total_size(self, total_size):
        self.total_size += total_size

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        folders = [Path(u.toLocalFile()) for u in event.mimeData().urls() if Path(u.toLocalFile()).is_dir()]
        logging.debug(folders)
        if folders:
            for folder in folders:
                self.list_widget.addItem(str(folder))
                # self.calculate_size_thread = CalculateSizeThread(folder)
                # self.calculate_size_thread.size_calculated.connect(self.update_total_size)
                # self.calculate_size_thread.start()


class DragDropListWidget(QListWidget):
    def __init__(self):
        super().__init__()


def main():
    """docstring for main"""
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s %(levelname)s: %(message)s')
    logging.getLogger(__name__)
    app = QApplication(sys.argv)
    ui = MainWidget()
    ui.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
