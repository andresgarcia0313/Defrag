# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
import sys
import subprocess
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QListWidget,
    QInputDialog,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QHBoxLayout,
)
from PySide6.QtCore import QThread, Signal

# Capa de Entidades (Entities)


class DiskPartition:
    def __init__(self, name, type_, size, free_space):
        self.name = name
        self.type = type_
        self.size = size
        self.free_space = free_space


class DefragTask:
    def __init__(self, partition: DiskPartition, sudo_password: str):
        self.partition = partition
        self.sudo_password = sudo_password
        self.progress = 0
        self.is_running = False
        self.message = ""

    def start(self):
        self.is_running = True
        self.progress = 0
        return f"Desfragmentación iniciada en {self.partition.name}"

    def stop(self):
        self.is_running = False
        self.progress = 100
        return f"Desfragmentación detenida en {self.partition.name}"

    def update_progress(self, progress, message=""):
        self.progress = progress
        self.message = message

# Capa de Casos de Uso (Use Cases)


class DefragUseCase:
    def __init__(self, task: DefragTask):
        self.task = task

    def start_defrag(self):
        return self.task.start()

    def stop_defrag(self):
        return self.task.stop()

    def update_progress(self, progress, message):
        self.task.update_progress(progress, message)

# Capa de Interfaces (Interface Adapters)


class DefragGUI(QWidget):
    def __init__(self, defrag_use_case: DefragUseCase):
        super().__init__()
        self.setWindowTitle("Defrag")
        self.setGeometry(300, 200, 780, 560)

        self.defrag_use_case = defrag_use_case
        self.defrag_worker = None
        self.partition = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Iniciar")
        self.stop_button = QPushButton("Detener")
        self.select_file_button = QPushButton("Seleccionar Archivo")

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.select_file_button)

        layout.addLayout(button_layout)

        self.partition_table = QTableWidget()
        self.partition_table.setColumnCount(4)
        self.partition_table.setHorizontalHeaderLabels(
            ["Unidad", "Tipo", "Tamaño", "Espacio libre"])
        self.partition_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.status_label = QLabel("Estado: Inactivo")
        self.progress_bar = QProgressBar()
        self.log_list = QListWidget()
        self.log_list.setSelectionMode(QListWidget.ExtendedSelection)

        layout.addWidget(self.partition_table)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_list)

        self.select_file_button.clicked.connect(self.select_file)
        self.start_button.clicked.connect(self.start_defrag)
        self.stop_button.clicked.connect(self.stop_defrag)
        self.partition_table.cellClicked.connect(self.select_partition)

        self.setLayout(layout)
        self.load_partitions()

    def load_partitions(self):
        try:
            result = subprocess.run(
                ['lsblk', '-o', 'NAME,TYPE,SIZE,FSAVAIL'], capture_output=True, text=True)
            lines = result.stdout.splitlines()
            self.partition_table.setRowCount(len(lines) - 1)
            for row, line in enumerate(lines[1:]):
                parts = line.split()
                for col, part in enumerate(parts):
                    self.partition_table.setItem(
                        row, col, QTableWidgetItem(part))
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudieron cargar las particiones: {str(e)}")

    def select_partition(self, row, column):
        name = self.partition_table.item(row, 0).text()
        type_ = self.partition_table.item(row, 1).text()
        size = self.partition_table.item(row, 2).text()
        free_space = self.partition_table.item(row, 3).text()

        self.partition = DiskPartition(name, type_, size, free_space)
        self.status_label.setText(
            f"Partición seleccionada: {self.partition.name}"
        )

    def start_defrag(self):
        if not self.partition:
            QMessageBox.warning(self, "Advertencia",
                                "Seleccione una partición antes de iniciar.")
            return

        sudo_password, ok = QInputDialog.getText(
            self, "Contraseña Sudo", "Introduzca su contraseña sudo:",
            QLineEdit.Password)
        if not ok or not sudo_password:
            QMessageBox.warning(
                self, "Advertencia", "Debe introducir la contraseña sudo para continuar.")
            return

        task = DefragTask(self.partition, sudo_password)
        defrag_use_case = DefragUseCase(task)

        response = defrag_use_case.start_defrag()
        self.status_label.setText(f"Estado: {response}")
        self.progress_bar.setValue(0)
        self.log_list.clear()

        self.defrag_worker = DefragWorker(task)
        self.defrag_worker.progress_signal.connect(self.update_progress)
        self.defrag_worker.start()

    def stop_defrag(self):
        if self.defrag_worker:
            self.defrag_worker.stop()
            self.defrag_worker.wait()
            response = self.defrag_use_case.stop_defrag()
            self.status_label.setText(f"Estado: {response}")
            self.progress_bar.setValue(0)
            self.log_list.addItem("Proceso detenido por el usuario.")

    def update_progress(self, progress, message):
        self.progress_bar.setValue(progress)
        self.log_list.addItem(message)

    def select_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo", "", "Todos los archivos (*)")
        if filepath:
            self.partition = DiskPartition(
                filepath, "Desconocido", "N/A", "N/A")
            self.status_label.setText(f"Archivo seleccionado: {filepath}")

# Capa de Infraestructura (Frameworks and Drivers)


class DefragWorker(QThread):
    progress_signal = Signal(int, str)

    def __init__(self, task: DefragTask):
        super().__init__()
        self.task = task
        self.running = True

    def run(self):
        try:
            process = subprocess.Popen(
                ["sudo", "-S", "e4defrag", "-c", self.task.partition.name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            process.stdin.write(self.task.sudo_password + "\n")
            process.stdin.flush()
            while self.running and process.poll() is None:
                output = process.stdout.readline().strip()
                if output:
                    self._parse_output(output)
            if process.poll() is not None and process.returncode != 0:
                error = process.stderr.read()
                self.progress_signal.emit(100, f"Error: {error}")
        except subprocess.CalledProcessError as e:
            self.progress_signal.emit(100, f"Error en el proceso: {str(e)}")
        except FileNotFoundError as e:
            self.progress_signal.emit(100, f"Archivo no encontrado: {str(e)}")
        except OSError as e:
            self.progress_signal.emit(
                100, f"Error del sistema operativo: {str(e)}")
        except ValueError as e:
            self.progress_signal.emit(100, f"Error de valor: {str(e)}")

    def stop(self):
        self.running = False

    def _parse_output(self, output):
        if "extents" in output:
            self.progress_signal.emit(50, output)
        elif "now" in output and "%" in output:
            try:
                progress = int(output.split()[-1].replace("%", ""))
                self.progress_signal.emit(progress, output)
            except ValueError:
                self.progress_signal.emit(0, output)
        else:
            self.progress_signal.emit(0, output)


def main():
    app = QApplication(sys.argv)

    window = DefragGUI(None)  # Asignar DefragUseCase cuando esté disponible
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
