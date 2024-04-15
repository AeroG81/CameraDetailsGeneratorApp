import sys
import os
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from etif import *


class combo(QComboBox):
    def __init__(self, title, parent):
        super(combo, self).__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        items = e.mimeData().text().replace("file:///", "").split("\n")
        for item in items:
            self.addItem(item)


class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    progress
        int indicating % progress

    '''
    finished = pyqtSignal()
    progress = pyqtSignal(int)

class Worker(QRunnable):
    """
    Link from https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/

    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    """

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.signals = WorkerSignals()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def getProgressSignal(self):
        return self.signals.progress

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        try:
            self.fn(*self.args, **self.kwargs)
        except Exception as e:
            debug("ERROR", Worker.run.__name__, e)
        finally:
            self.signals.finished.emit()  # Done


class MainApp(QMainWindow):
    def __init__(self):
        super(MainApp, self).__init__()
        self.threadpool = QThreadPool()
        print(
            "Multithreading with maximum %d threads" % self.threadpool.maxThreadCount()
        )
        self.settings = AppSettings(os.getcwd() + "/_internal/settings.json")
        self.BRAND_LOGO_PATH = (
            self.settings.getSettings().get("settings").get("Brand_Logo_Path")
        )
        self.generator = MetadataGenerator(self.BRAND_LOGO_PATH, self.settings)
        self.initUI()
        self.createActions()
        self.createMenus()

    def readBrandPathFiles(self):
        brand_files = os.listdir(self.BRAND_LOGO_PATH)
        # Filtering only the files.
        brand_files = [
            ".".join(f.split(".")[:-1]).capitalize()
            for f in brand_files
            if os.path.isfile(self.BRAND_LOGO_PATH + "/" + f)
        ]
        return brand_files

    def readImageSettings(self):
        file = self.files_combobox.currentText()
        if not file:
            return
        self.manual_photo_path = file
        self.manual_photo_settings = self.generator.readRawMetadata(file)
        settings = self.manual_photo_settings.get(file)
        brand_index = self.brand_files_list.index(
            str(settings.get("BRAND")).capitalize()
        )
        self.tab_manual_brand_combobox.setCurrentIndex(brand_index)
        self.tab_manual_Model_field.setText(str(settings.get("MODEL")))
        self.tab_manual_Focal_field.setText(str(settings.get("FOCALLENGTH")))
        self.tab_manual_ISO_field.setText(str(settings.get("ISO")))
        self.tab_manual_FStop_field.setText(str(settings.get("FNUMBER")))
        self.tab_manual_Exposure_field.setText(str(settings.get("EXPOSURE")))
        self.tab_manual_generate_button.setDisabled(False)

    def updateManualSettings(self):
        update_dict = {
            "BRAND": self.tab_manual_brand_combobox.currentText(),
            "MODEL": self.tab_manual_Model_field.text(),
            "FOCALLENGTH": self.tab_manual_Focal_field.text(),
            "ISO": self.tab_manual_ISO_field.text(),
            "FNUMBER": self.tab_manual_FStop_field.text(),
            "EXPOSURE": self.tab_manual_Exposure_field.text(),
            "ROTATION": self.tab_manual_Rotation_field.currentText(),
            "MIRROR": (
                True
                if self.tab_manual_mirror_images_checkbox.checkState() == Qt.Checked
                else False
            ),
        }
        original_dict = self.manual_photo_settings.get(self.manual_photo_path)
        updated_dict = {**original_dict, **update_dict}
        updated_dict = {self.manual_photo_path: updated_dict}
        debug(
            "DEBUG",
            MainApp.updateManualSettings.__name__,
            ("B4", self.manual_photo_settings),
        )
        self.manual_photo_settings = {**self.manual_photo_settings, **updated_dict}
        debug(
            "DEBUG",
            MainApp.updateManualSettings.__name__,
            ("AF", self.manual_photo_settings),
        )

    def createComputationTask(self, func, completed_callback):
        worker = Worker(func)
        callback = worker.getProgressSignal()
        self.generator.connectProgressCallback(callback)
        worker.signals.finished.connect(completed_callback)
        worker.signals.progress.connect(self.updateProgressBar)
        self.threadpool.start(worker)

    def updateProgressBar(self, progress):
        self.progress_bar.setValue(progress)
        QApplication.processEvents()

    def showProgressBar(self):
        self.progress_bar.show()
        self.progress_bar_label.show()

    def hideProgressBar(self):
        self.progress_bar.hide()
        self.progress_bar_label.hide()

    def generateSingleCover(self):
        current_index = self.files_combobox.currentIndex()
        files = self.files_combobox.currentText()
        debug("DEBUG", MainApp.generateSingleCover.__name__, files)
        self.generateCover(files)
        self.files_combobox.removeItem(current_index)

    def generateAllCover(self):
        files = [
            self.files_combobox.itemText(i) for i in range(self.files_combobox.count())
        ]
        # print(files)
        debug("DEBUG", MainApp.generateAllCover.__name__, files)
        self.generateCover(files)
        self.files_combobox.clear()

    def generateCoverBasedOnSettings(self):
        file = self.files_combobox.currentText()
        debug("DEBUG", MainApp.generateCoverBasedOnSettings.__name__, file)
        if not file:
            debug(
                "ERROR", MainApp.generateCoverBasedOnSettings.__name__, "FILE IS EMPTY"
            )
            return
        if self.manual_photo_settings.get(file, None) is None:
            debug(
                "ERROR",
                MainApp.generateCoverBasedOnSettings.__name__,
                "FILE SETTINGS DOES NOT EXIST",
            )
            return
        self.showProgressBar()

        self.updateManualSettings()

        show_images = (
            True
            if self.tab_manual_show_generated_images_checkbox.checkState() == Qt.Checked
            else False
        )
        combine_images = (
            True
            if self.tab_manual_combine_images_checkbox.checkState() == Qt.Checked
            else False
        )
        self.createComputationTask(
            lambda: self.generator.execSettings(self.manual_photo_settings, show_images, combine_images),
            self.hideProgressBar
        )

    def generateCover(self, files):
        if not files:
            return
        self.showProgressBar()

        show_images = (
            True
            if self.tab_auto_show_generated_images_checkbox.checkState() == Qt.Checked
            else False
        )
        combine_images = (
            True
            if self.tab_auto_combine_images_checkbox.checkState() == Qt.Checked
            else False
        )

        self.createComputationTask(
            lambda: self.generator.exec(files, show_images, combine_images), 
            self.hideProgressBar
        )

    def createActions(self):
        self.openAct = QAction("&Open...", self, shortcut="Ctrl+O", triggered=self.open)
        self.generateCoverAct = QAction(
            "&AutoGenerate", self, shortcut="Ctrl+G", triggered=self.generateSingleCover
        )
        self.generateCoverAllAct = QAction(
            "&AutoGenerateAll", self, shortcut="Ctrl+A", triggered=self.generateAllCover
        )

    def createMenus(self):
        self.fileMenu = QMenu("&File", self)
        self.fileMenu.addAction(self.openAct)
        # self.fileMenu.addAction()
        # self.fileMenu.addSeparator()
        # self.fileMenu.addAction()
        self.runMenu = QMenu("&Run", self)
        self.runMenu.addAction(self.generateCoverAct)
        self.runMenu.addAction(self.generateCoverAllAct)
        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.runMenu)

    def open(self):
        options = QFileDialog.Options()
        # fileName = QFileDialog.getOpenFileName(self, "Open File", QDir.currentPath())
        fileName, _ = QFileDialog.getOpenFileNames(
            self,
            "QFileDialog.getOpenFileNames()",
            "",
            "Images (*.png *.jpeg *.jpg *.bmp *.cr2 *.raf *.raw)",
            options=options,
        )
        self.files_combobox.addItems(fileName)
        # if fileName:
        #     image = QImage(fileName)
        #     if image.isNull():
        #         QMessageBox.information(
        #             self, "Image Viewer", "Cannot load %s." % fileName
        #         )
        #         return

        #     self.imageLabel.setPixmap(QPixmap.fromImage(image))
        #     self.scaleFactor = 1.0

        #     self.scrollArea.setVisible(True)
        #     self.printAct.setEnabled(True)
        #     self.fitToWindowAct.setEnabled(True)
        #     self.updateActions()

        #     if not self.fitToWindowAct.isChecked():
        #         self.imageLabel.adjustSize()

    def initTabAutoUI(self):
        self.tab_auto_generate = QWidget()
        self.tab_auto_generate.layout = QVBoxLayout()

        # Check box to show generated image
        self.tab_auto_show_generated_images_checkbox = QCheckBox(self.tab_auto_generate)
        self.tab_auto_show_generated_images_checkbox.setText("Show Generated Images")
        self.tab_auto_generate.layout.addWidget(
            self.tab_auto_show_generated_images_checkbox
        )

        # Check box to combine generated image with original image
        self.tab_auto_combine_images_checkbox = QCheckBox(self.tab_auto_generate)
        self.tab_auto_combine_images_checkbox.setText(
            "(BETA) Combine Original Images with Cover"
        )
        self.tab_auto_generate.layout.addWidget(self.tab_auto_combine_images_checkbox)

        # Generate button to generate single camera settings photo selected in combobox
        self.tab_auto_generate_button = QPushButton(self.tab_auto_generate)
        self.tab_auto_generate_button.setText("Generate")
        self.tab_auto_generate_button.clicked.connect(self.generateSingleCover)
        self.tab_auto_generate.layout.addWidget(self.tab_auto_generate_button)

        # Generate button to generate all camera settings photo in combobox
        self.tab_auto_generate_all_button = QPushButton(self.tab_auto_generate)
        self.tab_auto_generate_all_button.setText("Generate All")
        self.tab_auto_generate_all_button.clicked.connect(self.generateAllCover)
        self.tab_auto_generate.layout.addWidget(self.tab_auto_generate_all_button)

        self.tab_auto_generate.setLayout(self.tab_auto_generate.layout)

    def initTabManualUI(self):
        self.tab_manual_generate = QWidget()
        self.tab_manual_generate.layout = QVBoxLayout()

        # Generate button to generate single camera settings photo selected in combobox
        self.tab_manual_read_settings_button = QPushButton(self.tab_manual_generate)
        self.tab_manual_read_settings_button.setText("Read Settings")
        self.tab_manual_read_settings_button.clicked.connect(self.readImageSettings)
        self.tab_manual_generate.layout.addWidget(self.tab_manual_read_settings_button)

        # brand selection field for manually edit camera brand settings
        self.tab_manual_group_brand = QWidget(self.tab_manual_generate)
        self.tab_manual_group_brand.layout = QVBoxLayout()
        self.tab_manual_brand_label = QLabel(self.tab_manual_group_brand)
        self.tab_manual_brand_label.setText("Brand")
        self.tab_manual_brand_combobox = QComboBox(self.tab_manual_generate)
        self.brand_files_list = self.readBrandPathFiles()
        self.tab_manual_brand_combobox.addItems(self.brand_files_list)
        self.tab_manual_group_brand.layout.addWidget(self.tab_manual_brand_label)
        self.tab_manual_group_brand.layout.addWidget(self.tab_manual_brand_combobox)
        self.tab_manual_group_brand.setLayout(self.tab_manual_group_brand.layout)
        self.tab_manual_generate.layout.addWidget(self.tab_manual_group_brand)

        # Model edit field for manually edit camera Model settings
        self.tab_manual_group_Model = QWidget(self.tab_manual_generate)
        self.tab_manual_group_Model.layout = QHBoxLayout()
        self.tab_manual_Model_label = QLabel(self.tab_manual_group_Model)
        self.tab_manual_Model_label.setText("Model")
        self.tab_manual_Model_field = QLineEdit(self.tab_manual_group_Model)
        self.tab_manual_group_Model.layout.addWidget(self.tab_manual_Model_label)
        self.tab_manual_group_Model.layout.addWidget(self.tab_manual_Model_field)
        self.tab_manual_group_Model.setLayout(self.tab_manual_group_Model.layout)
        self.tab_manual_generate.layout.addWidget(self.tab_manual_group_Model)

        # Focal edit field for manually edit camera Focal settings
        self.tab_manual_group_Focal = QWidget(self.tab_manual_generate)
        self.tab_manual_group_Focal.layout = QHBoxLayout()
        self.tab_manual_Focal_label = QLabel(self.tab_manual_group_Focal)
        self.tab_manual_Focal_label.setText("Focal")
        self.tab_manual_Focal_field = QLineEdit(self.tab_manual_group_Focal)
        self.tab_manual_group_Focal.layout.addWidget(self.tab_manual_Focal_label)
        self.tab_manual_group_Focal.layout.addWidget(self.tab_manual_Focal_field)
        self.tab_manual_group_Focal.setLayout(self.tab_manual_group_Focal.layout)
        self.tab_manual_generate.layout.addWidget(self.tab_manual_group_Focal)

        # ISO edit field for manually edit camera ISO settings
        self.tab_manual_group_ISO = QWidget(self.tab_manual_generate)
        self.tab_manual_group_ISO.layout = QHBoxLayout()
        self.tab_manual_ISO_label = QLabel(self.tab_manual_group_ISO)
        self.tab_manual_ISO_label.setText("ISO")
        self.tab_manual_ISO_field = QLineEdit(self.tab_manual_group_ISO)
        self.tab_manual_group_ISO.layout.addWidget(self.tab_manual_ISO_label)
        self.tab_manual_group_ISO.layout.addWidget(self.tab_manual_ISO_field)
        self.tab_manual_group_ISO.setLayout(self.tab_manual_group_ISO.layout)
        self.tab_manual_generate.layout.addWidget(self.tab_manual_group_ISO)

        # FStop edit field for manually edit camera FStop settings
        self.tab_manual_group_FStop = QWidget(self.tab_manual_generate)
        self.tab_manual_group_FStop.layout = QHBoxLayout()
        self.tab_manual_FStop_label = QLabel(self.tab_manual_group_FStop)
        self.tab_manual_FStop_label.setText("FStop")
        self.tab_manual_FStop_field = QLineEdit(self.tab_manual_group_FStop)
        self.tab_manual_group_FStop.layout.addWidget(self.tab_manual_FStop_label)
        self.tab_manual_group_FStop.layout.addWidget(self.tab_manual_FStop_field)
        self.tab_manual_group_FStop.setLayout(self.tab_manual_group_FStop.layout)
        self.tab_manual_generate.layout.addWidget(self.tab_manual_group_FStop)

        # Exposure edit field for manually edit camera Exposure settings
        self.tab_manual_group_Exposure = QWidget(self.tab_manual_generate)
        self.tab_manual_group_Exposure.layout = QHBoxLayout()
        self.tab_manual_Exposure_label = QLabel(self.tab_manual_group_Exposure)
        self.tab_manual_Exposure_label.setText("Exposure")
        self.tab_manual_Exposure_field = QLineEdit(self.tab_manual_group_Exposure)
        self.tab_manual_group_Exposure.layout.addWidget(self.tab_manual_Exposure_label)
        self.tab_manual_group_Exposure.layout.addWidget(self.tab_manual_Exposure_field)
        self.tab_manual_group_Exposure.setLayout(self.tab_manual_group_Exposure.layout)
        self.tab_manual_generate.layout.addWidget(self.tab_manual_group_Exposure)

        # Rotation edit field for manually edit camera Rotation settings
        self.tab_manual_group_Rotation = QWidget(self.tab_manual_generate)
        self.tab_manual_group_Rotation.layout = QHBoxLayout()
        self.tab_manual_Rotation_label = QLabel(self.tab_manual_group_Rotation)
        self.tab_manual_Rotation_label.setText("Rotation")
        self.tab_manual_Rotation_field = QComboBox(self.tab_manual_group_Rotation)
        self.tab_manual_Rotation_field.addItems(
            ["0", "45", "90", "135", "180", "225", "270", "315"]
        )
        self.tab_manual_mirror_images_checkbox = QCheckBox(self.tab_manual_generate)
        self.tab_manual_mirror_images_checkbox.setText("Mirror Image")
        self.tab_manual_group_Rotation.layout.addWidget(self.tab_manual_Rotation_label)
        self.tab_manual_group_Rotation.layout.addWidget(self.tab_manual_Rotation_field)
        self.tab_manual_group_Rotation.layout.addWidget(
            self.tab_manual_mirror_images_checkbox
        )
        self.tab_manual_group_Rotation.setLayout(self.tab_manual_group_Rotation.layout)
        self.tab_manual_generate.layout.addWidget(self.tab_manual_group_Rotation)

        # Check box to show generated image
        self.tab_manual_show_generated_images_checkbox = QCheckBox(
            self.tab_manual_generate
        )
        self.tab_manual_show_generated_images_checkbox.setText("Show Generated Image")
        self.tab_manual_generate.layout.addWidget(
            self.tab_manual_show_generated_images_checkbox
        )

        # Check box to combine generated image with original image
        self.tab_manual_combine_images_checkbox = QCheckBox(self.tab_manual_generate)
        self.tab_manual_combine_images_checkbox.setText(
            "(BETA) Combine Original Images with Cover"
        )
        self.tab_manual_generate.layout.addWidget(
            self.tab_manual_combine_images_checkbox
        )

        # Generate button to generate single camera settings photo selected in combobox
        self.tab_manual_generate_button = QPushButton(self.tab_manual_generate)
        self.tab_manual_generate_button.setText("Generate")
        self.tab_manual_generate_button.setDisabled(True)
        self.tab_manual_generate_button.clicked.connect(
            self.generateCoverBasedOnSettings
        )
        self.tab_manual_generate.layout.addWidget(self.tab_manual_generate_button)

        self.tab_manual_generate.setLayout(self.tab_manual_generate.layout)

    def initUI(self):
        layout = QVBoxLayout()
        self.files_label = QLabel("Drag & Drop files here or open from File Menu")
        self.files_combobox = combo("Files", self)
        self.files_combobox.move(100, 20)
        layout.addWidget(self.files_label)
        layout.addWidget(self.files_combobox)

        self.initTabAutoUI()
        self.initTabManualUI()

        self.tab = QTabWidget()
        self.tab.addTab(self.tab_auto_generate, "Auto")
        self.tab.addTab(self.tab_manual_generate, "Manual")

        layout.addWidget(self.tab)

        self.progress_bar = QProgressBar(self)
        self.progress_bar_label = QLabel("Generating Camera Settings")
        self.progress_bar.hide()
        self.progress_bar_label.hide()
        # Connect generator class to progress bar in order to update the progress of generation
        self.generator.connectToProgressBar(self.progress_bar)

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_bar_label)

        # self.setLayout(layout)
        # self.setGeometry(200,200,400,200)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.setWindowTitle("Photo Settings Generator")
        # self.resize(800, 600)

def main():
    app = QApplication(sys.argv)
    ex = MainApp()
    ex.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
