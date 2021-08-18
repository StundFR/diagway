# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DiagwayProjection
                                 A QGIS plugin
 Projection de route
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-06-29
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Cochet Quentin / Diagway
        email                : quentin.cochet@outlook.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from os import error
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QProgressBar, QPushButton
from qgis.core import QgsMapLayerProxyModel, QgsMessageLog, Qgis

# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the DockWidget
from .DiagwayProjection_dockwidget import DiagwayProjectionDockWidget
from .Layer import QgsLayer
from .WorkerAuto import WorkerAuto
from .WorkerFullAuto import WorkerFullAuto
from .WorkerDistance import WorkerDistance
from .Tools import *
import os.path

LAYER_STATEMENT_NAME = "Statement_source"

class DiagwayProjection(QtCore.QObject):
    """Constructor & Variables"""
    def __init__(self, iface):
        #Multi-threading
        QtCore.QObject.__init__(self)
        self.layer_source = None
        self.layer_dest = None
        self.path_csv = None

        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'DiagwayProjection_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&DiagwayProjection')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'DiagwayProjection')
        self.toolbar.setObjectName(u'DiagwayProjection')

        #print "** INITIALIZING DiagwayProjection"
        self.pluginIsActive = False
        self.dockwidget = None
    #--------------------------------------------------------------------------

    """Function for the plugins"""
    #Get the translation for a string using Qt translation API
    def tr(self, message):
        """
        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('DiagwayProjection', message)

    #Add a toolbar icon to the toolbar
    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """
        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    #Create the menu entries and toolbar icons inside the QGIS GUI
    def initGui(self):
        icon_path = ':/plugins/DiagwayProjection/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'DiagwayProjection'),
            callback=self.run,
            parent=self.iface.mainWindow())

    #Cleanup necessary items here when plugin dockwidget is closed
    def onClosePlugin(self):
        #disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        #self.dockwidget = None
        self.pluginIsActive = False

    #Removes the plugin menu item and icon from QGIS GUI
    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&DiagwayProjection'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar
    #--------------------------------------------------------------------------

    """Function for the algorithm"""
    #Create the path for the CSV file (Replace file)
    def saveFile(self):
        filename, _filter = QFileDialog.getSaveFileName(self.dockwidget, "Select output file ","", '*.csv')
        self.dockwidget.lineEdit_file.setText(filename)

    #Create the path for the CSV file (Complete file)
    def selectFile(self):
        filename, _filter = QFileDialog.getOpenFileName(self.dockwidget, "Select output file ","", '*.csv')
        self.dockwidget.lineEdit_file_complete.setText(filename)

    #Get source, destination layer and the CSV path
    def initSourceDestFile(self):
        path_dir = getPath()

        if (self.dockwidget.radio_a.isChecked()):
            self.path_csv = self.dockwidget.lineEdit_file_complete.text()
            layer_source = self.dockwidget.comboBox_layers_source_complete.currentLayer()
            layer_dest = self.dockwidget.comboBox_layers_dest_complete.currentLayer()

            with open(self.path_csv, "r") as csv:
                header = csv.readline()

            self.field_source, self.field_dest = header.split(";")
            self.field_dest = self.field_dest[:-1]
        else:
            self.path_csv = self.dockwidget.lineEdit_file.text()
            layer_source = self.dockwidget.comboBox_layers_source.currentLayer()
            layer_dest = self.dockwidget.comboBox_layers_dest.currentLayer()
            self.field_source = self.dockwidget.comboBox_fields_source.currentText()
            self.field_dest = self.dockwidget.comboBox_fields_dest.currentText()

        self.layer_source = QgsLayer(vectorLayer=layer_source)
        self.layer_dest = QgsLayer(vectorLayer=layer_dest)

        if not self.layer_source.isLT93():
            self.layer_source = self.layer_source.projectionLT93("{}/{}_LT93.shp".format(path_dir, self.layer_source.name))
            QgsLayer.removeLayersByName(layer_source.name())
            self.layer_source.add()

        if not self.layer_dest.isLT93():
            self.layer_dest = self.layer_dest.projectionLT93("{}/{}_LT93.shp".format(path_dir, self.layer_dest.name))
            QgsLayer.removeLayersByName(layer_dest.name())
            self.layer_dest.add()

        if not self.layer_source.isFieldExist(self.field_source):
            self.field_source = self.field_source[:-2]
            
        if not self.layer_dest.isFieldExist(self.field_dest):
            self.field_dest = self.field_dest[:-2]

    #Filled the combo box fields
    def fillComboBoxWithFields(self, comboBox):
        comboBox.clear()
        layer = self.dockwidget.sender().currentLayer()
        if layer is not None:
            fields = layer.fields()
            for f in fields:
                comboBox.addItem(f.name())

    #Check if all box are correct for page3
    def checkCorrespondance(self):
        if (self.dockwidget.radio_a.isChecked()):
            path_csv = self.dockwidget.lineEdit_file_complete.text()
            layer_source = self.dockwidget.comboBox_layers_source_complete.currentLayer()
            layer_dest = self.dockwidget.comboBox_layers_dest_complete.currentLayer()
        else:
            path_csv = self.dockwidget.lineEdit_file.text()
            layer_source = self.dockwidget.comboBox_layers_source.currentLayer()
            layer_dest = self.dockwidget.comboBox_layers_dest.currentLayer()

        check = ((layer_source != layer_dest) and (layer_source != None) and (layer_dest != None) and (path_csv != ""))

        if (self.dockwidget.radio_w.isChecked()):
            self.dockwidget.push_next.setEnabled(check)
        else:
            self.dockwidget.push_next_complete.setEnabled(check)

    #Check if we can run calcul distane
    def checkCalculDistance(self):
        check_db = (self.dockwidget.lineEdit_database.text() != "")
        check_host = (self.dockwidget.lineEdit_host.text() != "")
        check_port = (self.dockwidget.lineEdit_port.text() != "")
        check_generate = self.dockwidget.checkBox_regenerate.isChecked()
        items_source = self.dockwidget.listWidget_fields_source.selectedItems()
        items_dest = self.dockwidget.listWidget_fields_dest.selectedItems()
        check_source = (sum(1 for _ in items_source) > 0)
        check_dest = (sum(1 for _ in items_dest) > 0)

        check = check_db and check_host and check_port and ((check_source and check_dest) or not check_generate)
        self.dockwidget.push_calcul_page4.setEnabled(check)

    #Display the prewiew of a file in 
    def fillPreviewWithFile(self):
        path_csv = self.dockwidget.lineEdit_file_complete.text()
        try:
            with open(path_csv, "r") as csv:
                text = csv.read()
        except (FileNotFoundError, OSError):
            text = "File doesn't exist"
            self.dockwidget.push_next_complete.setEnabled(False)
        except UnicodeDecodeError :
            text = "Unicode error"
            self.dockwidget.push_next_complete.setEnabled(False)
        finally:
            self.dockwidget.textEdit_preview.setText(text)

    #Makes the preparations for the projection
    def setupCorrespondance(self):
        self.initSourceDestFile()
        self.layer_source.filter("")
        self.layer_dest.filter("")
        self.dockwidget.checkBox_symbolized_page3.setEnabled(False)

        if (self.dockwidget.radio_w.isChecked()):
            line = "{};{}\n".format(self.field_source, self.field_dest)
            with open(self.path_csv, "w") as csv:
                csv.write(line)
           
        self.dockwidget.label_field_source.setText(self.field_source + " :")
        self.dockwidget.label_field_dest.setText(self.field_dest + " :")

        if self.isSymbolizedChecked():
            self.layer_source.setSymbol(0.8, QColor("orange"))
            self.layer_dest.setSymbol(0.8, QColor(139,69,19)) #Brown
            self.dockwidget.checkBox_symbolized_page3.setChecked(True)
        else:
            self.dockwidget.checkBox_symbolized_page3.setChecked(False)
        self.dockwidget.checkBox_symbolized_page3.setEnabled(True)

        self.layer_source.labeling(10, self.field_source, QColor("orange"))
        self.layer_dest.labeling(10, self.field_dest, QColor(139,69,19)) #Brown

        name = getNameFromPath(self.path_csv)
        QgsLayer.removeLayersByName(name)
        self.iface.addVectorLayer(self.path_csv, "", "ogr")

        layer_statement = self.layer_source.clone()
        layer_statement.setName(LAYER_STATEMENT_NAME)

        QgsLayer.removeLayersByName(LAYER_STATEMENT_NAME)

        layer_statement.add()
        layer_statement.labeling(10, self.field_source, QColor("green"))
        layer_statement.setVisibility(False)

        QgsLayer.styleByCSV(layer_statement, self.path_csv)

        self.dockwidget.checkBox_symbolized_page3.enabled = True
            
    #Makes the preparations for the calcul distance
    def setupCalculDistance(self):
        listWidget_source = self.dockwidget.listWidget_fields_source
        listWidget_dest = self.dockwidget.listWidget_fields_dest
        fields_source = self.layer_source.getFields()
        fields_dest = self.layer_dest.getFields()

        listWidget_source.clear()
        for f in fields_source:
            listWidget_source.addItem(f)
        listWidget_dest.clear()
        for f in fields_dest:
            listWidget_dest.addItem(f)

        self.dockwidget.layer_name_source.setText("{} :".format(self.layer_source.name))
        self.dockwidget.layer_name_dest.setText("{} :".format(self.layer_dest.name))

    #Check if all parameters are goods for the auto button
    def checkWorkerAuto(self):
        txt = self.dockwidget.lineEdit_fields_source.text()
        buffer_distance = self.dockwidget.lineEdit_buffer_distance.text()
        precision = self.dockwidget.lineEdit_precision.text()

        try:
            buffer_distance = int(buffer_distance)
            precision = int(precision)
        except ValueError:
            self.dockwidget.push_auto.setEnabled(False)
            #print("Value have to be an integer")
        else:
            if (txt == ""):
                self.dockwidget.push_auto.setEnabled(False)
            else :
                self.dockwidget.push_auto.setEnabled(True)

    #Check if all parameters are goods for the fullAuto button
    def checkWorkerFullAuto(self):
        buffer_distance = self.dockwidget.lineEdit_buffer_distance.text()
        precision = self.dockwidget.lineEdit_precision.text()

        try:
            buffer_distance = int(buffer_distance)
            precision = int(precision)
        except ValueError:
            self.dockwidget.push_fullauto.setEnabled(False)
            #print("Value have to be an integer")
        else:
            self.dockwidget.push_fullauto.setEnabled(True)

    #Check if all parameters are goods for the add button
    def checkAddButton(self):
        textEdit_source = self.dockwidget.lineEdit_fields_source.text()
        textEdit_dest = self.dockwidget.lineEdit_fields_dest.text()

        if ((textEdit_dest == "") or (textEdit_source == "")):
            self.dockwidget.push_add.setEnabled(False)
        else:
            self.dockwidget.push_add.setEnabled(True)

    #Add on the widget the entitys selected
    def getSelectedEntity(self):
        fields_source = ""
        fields_dest = ""
        
        if (self.layer_source is not None):
            feats_source = self.layer_source.selectedFeatures()
            for f in feats_source:
                fields_source += str(f[self.field_source]) + ";"

        if (self.layer_dest is not None):
            destination_feats = self.layer_dest.selectedFeatures()
            for f in destination_feats:
                try:
                    fields_dest += str(f[self.field_dest]) + ";"
                except KeyError:
                    fields_dest += str(f[self.field_dest]) + ";"

        fields_source = fields_source[:-1]
        fields_dest = fields_dest[:-1]

        if (fields_source != ""):
            self.dockwidget.lineEdit_fields_source.setText(fields_source)
        self.dockwidget.lineEdit_fields_dest.setText(fields_dest)       

    #Add fields of a layer in comboBox
    def addToCSV(self):
        text_source = self.dockwidget.lineEdit_fields_source.text()
        text_dest = self.dockwidget.lineEdit_fields_dest.text()

        addLineCSV(self.path_csv, text_source, text_dest)

        self.dockwidget.lineEdit_fields_source.setText("")
        self.dockwidget.lineEdit_fields_dest.setText("")

        createLayerStyleByCSV(self.path_csv)

        self.iface.mapCanvas().refreshAllLayers() 

    #Switch between layer
    def switch(self):
        layer_statement = QgsLayer.findLayerByName(LAYER_STATEMENT_NAME)

        layers = [self.layer_source, self.layer_dest] 

        if (self.layer_source.isVisible()):
            visibility = False
        else:
            visibility = True

        for l in layers:
            l.setVisibility(visibility)

        layer_statement.setVisibility(not visibility)

    #Select entity when you put a value in source lineEdit
    def showCorrespondance(self):
        textEdit_dest = self.dockwidget.lineEdit_fields_dest
        field_source_value = self.sender().text()
        

        with open(self.path_csv, "r") as csv:
            lines = csv.readlines()

        for line in lines:
            id = line.split("\"")[0]
            id = id[:-1]
            if (field_source_value == id):
                field_dest_value = line.split("\"")[1]
                textEdit_dest.setText(field_dest_value)

                expression_dest = "\"{}\" = {}".format(self.field_source, field_source_value)
                expression_source = "\"{}\" in ('{}')".format(self.field_dest, field_dest_value.replace(";", "','"))

                source_statement = QgsLayer.findLayerByName(LAYER_STATEMENT_NAME)

                source_statement.setVisibility(False)
                self.layer_source.setVisibility(True)
                self.layer_dest.setVisibility(True)

                self.layer_dest.filter(expression_source)
                self.layer_dest.zoom(self)
                self.layer_dest.filter("")

                self.layer_source.selectByExpression(expression_dest)
                self.layer_dest.selectByExpression(expression_source)
                return

        textEdit_dest.setText("")
    
    #Display/hide label of layers
    def showLabeling(self, layer):
        check = self.sender().isChecked()
        layer.setLabel(check)
        layer.vector.triggerRepaint()

    #Clear all the csv execpt the header
    def clearCSV(self, path_csv):
        with open(path_csv, "r") as csv:
            header = csv.readline()
        with open(path_csv, "w") as csv:
            csv.write(header)

        createLayerStyleByCSV(path_csv)
        self.iface.mapCanvas().refreshAllLayers() 
        self.iface.messageBar().pushMessage("Done", "CSV cleared", level=3, duration=4)
    
    #Zoom on source value entity
    def zoomSource(self):
        
        value = self.dockwidget.lineEdit_fields_source.text()
        expression = "{} = {}".format(self.field_source, value)

        if self.layer_source.filter(expression) and value != "":
            self.layer_source.zoom(self)
        else:
            self.iface.messageBar().pushMessage("Error", "Incorrect source value", level=1, duration=4)
        self.layer_source.filter("")

    #Check if automatic symbol is checked
    def isSymbolizedChecked(self):
        if self.dockwidget.checkBox_symbolized_page3.isEnabled():
            return self.dockwidget.checkBox_symbolized_page3.isChecked()
        else:
            if self.dockwidget.radio_a.isChecked():
                return self.dockwidget.checkBox_symbolized_complete.isChecked()
            elif self.dockwidget.radio_w.isChecked():
                return self.dockwidget.checkBox_symbolized_create.isChecked()
            else:
                return False
    #--------------------------------------------------------------------------
    """Algo Multithreading"""
    """Auto function"""
    def startAuto(self):
        source_value = self.dockwidget.lineEdit_fields_source.text()
        buffer_distance = int(self.dockwidget.lineEdit_buffer_distance.text())
        precision = float(self.dockwidget.lineEdit_precision.text())/100
        auto_symbol = self.isSymbolizedChecked()

        worker = WorkerAuto(self.layer_source, self.layer_dest, source_value, self.field_source, self.field_dest, buffer_distance, precision, auto_symbol)

        # configure the QgsMessageBar
        messageBar = self.iface.messageBar().createMessage('Running...', )
        self.iface.messageBar().pushWidget(messageBar)
        self.messageBar = messageBar

        # start the worker in a new thread
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        worker.finished.connect(self.autoFinished)
        worker.error.connect(self.algoError)
        thread.started.connect(worker.run)
        thread.start()
        self.thread = thread
        self.worker = worker

    def autoFinished(self, line, expression_source, expression_dest):
        # clean up the worker and thread
        self.worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        # remove widget from message bar
        self.iface.messageBar().popWidget(self.messageBar)

        if line != "":
            # report the result    
            self.iface.messageBar().pushMessage("Done", "Roads found", level=3, duration=4)
        else:
            # notify the user that something went wrong
            self.iface.messageBar().pushMessage("Done", "Roads not found", level=4, duration=4)

        self.dockwidget.lineEdit_fields_dest.setText(line)
        self.worker.layer_source.selectByExpression(expression_source)
        self.worker.layer_dest.selectByExpression(expression_dest)


    """Full auto function"""
    def startFullAuto(self):
        buffer_distance = int(self.dockwidget.lineEdit_buffer_distance.text())
        precision = float(self.dockwidget.lineEdit_precision.text())/100
        worker = WorkerFullAuto(self.layer_source, self.layer_dest, self.path_csv, self.field_source, self.field_dest, buffer_distance, precision)

        # configure the QgsMessageBar
        messageBar = self.iface.messageBar().createMessage('Running...', )
        progressBar = QProgressBar()
        progressBar.setAlignment(QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        cancelButton = QPushButton()
        cancelButton.setText('Cancel')
        cancelButton.clicked.connect(worker.kill)
        messageBar.layout().addWidget(progressBar)
        messageBar.layout().addWidget(cancelButton)
        self.iface.messageBar().pushWidget(messageBar)
        self.messageBar = messageBar

        # start the worker in a new thread
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        worker.finished.connect(self.fullAutoFinished)
        worker.error.connect(self.algoError)
        worker.progress.connect(progressBar.setValue)
        thread.started.connect(worker.run)
        thread.start()
        self.thread = thread
        self.worker = worker

    def fullAutoFinished(self, layer):
        # clean up the worker and thread
        self.worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        # remove widget from message bar
        self.iface.messageBar().popWidget(self.messageBar)
        if layer is not None:
            # report the result
            self.iface.messageBar().pushMessage("Done", "Algorith is finished", level=3, duration=4)
        else:
            # notify the user that something went wrong
            self.iface.messageBar().pushMessage("Error", "Something went wrong... Check out the logs message for further informations", level=4, duration=4)


    """Calcul distance function"""
    def startDistance(self):
        DATABASE = self.dockwidget.lineEdit_database.text()
        HOST = self.dockwidget.lineEdit_host.text()
        USER = self.dockwidget.lineEdit_user.text()
        PASSWORD = self.dockwidget.lineEdit_password.text()
        PORT = self.dockwidget.lineEdit_port.text()
        regenerate = self.dockwidget.checkBox_regenerate.isChecked()
        add = self.dockwidget.checkBox_add.isChecked()
        items_source = self.dockwidget.listWidget_fields_source.selectedItems()
        items_dest = self.dockwidget.listWidget_fields_dest.selectedItems()
        fields_source = [i.text() for i in items_source]
        fields_dest = [i.text() for i in items_dest]
        worker = WorkerDistance(DATABASE, HOST, USER, PASSWORD, PORT, regenerate, add, self.layer_source, self.layer_dest, self.path_csv, self.field_source, self.field_dest, fields_source, fields_dest)

        # configure the QgsMessageBar
        messageBar = self.iface.messageBar().createMessage('Running...', )
        self.iface.messageBar().pushWidget(messageBar)
        self.messageBar = messageBar

        # start the worker in a new thread
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        worker.finished.connect(self.distanceFinished)
        worker.error.connect(self.algoError)
        thread.started.connect(worker.run)
        thread.start()
        self.thread = thread
        self.worker = worker

    def distanceFinished(self, nb):
        # clean up the worker and thread
        self.worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        # remove widget from message bar
        self.iface.messageBar().popWidget(self.messageBar)
        if nb:
            # report the result
            self.iface.messageBar().pushMessage("Done", "Algorith is finished", level=3, duration=4)
        else:
            # notify the user that something went wrong
            self.iface.messageBar().pushMessage("Error", "Something went wrong... Check out the logs message for further informations", level=4, duration=4)

    def algoError(self, e, exception_string):
        QgsMessageLog.logMessage('Worker thread raised an exception: {} -- {}'.format(exception_string, e), level=Qgis.Critical)
    #--------------------------------------------------------------------------

    """Run"""
    def run(self):
        if not self.pluginIsActive:
            self.pluginIsActive = True

            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = DiagwayProjectionDockWidget()

                #Reset index layer
                self.dockwidget.comboBox_layers_source.setCurrentIndex(-1)
                self.dockwidget.comboBox_layers_dest.setCurrentIndex(-1)
                self.dockwidget.comboBox_layers_source_complete.setCurrentIndex(-1)
                self.dockwidget.comboBox_layers_dest_complete.setCurrentIndex(-1)

                #Filter for vector layer
                self.dockwidget.comboBox_layers_source.setFilters(QgsMapLayerProxyModel.VectorLayer)
                self.dockwidget.comboBox_layers_dest.setFilters(QgsMapLayerProxyModel.VectorLayer)
                self.dockwidget.comboBox_layers_source_complete.setFilters(QgsMapLayerProxyModel.VectorLayer)
                self.dockwidget.comboBox_layers_dest_complete.setFilters(QgsMapLayerProxyModel.VectorLayer)

                #Display fields of selected layers
                self.dockwidget.comboBox_layers_source.layerChanged.connect(lambda : self.fillComboBoxWithFields(self.dockwidget.comboBox_fields_source))
                self.dockwidget.comboBox_layers_dest.layerChanged.connect(lambda : self.fillComboBoxWithFields(self.dockwidget.comboBox_fields_dest))

                #Check before go to next step
                self.dockwidget.comboBox_layers_source.layerChanged.connect(self.checkCorrespondance)
                self.dockwidget.comboBox_layers_dest.layerChanged.connect(self.checkCorrespondance)
                self.dockwidget.lineEdit_file.textChanged.connect(self.checkCorrespondance)
                self.dockwidget.comboBox_layers_source_complete.layerChanged.connect(self.checkCorrespondance)
                self.dockwidget.comboBox_layers_dest_complete.layerChanged.connect(self.checkCorrespondance)
                self.dockwidget.lineEdit_file_complete.textChanged.connect(self.checkCorrespondance)

                #Connect buttons
                self.dockwidget.push_cancel_create.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(0))
                self.dockwidget.push_cancel_complete.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(0))
                self.dockwidget.push_cancel_3.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(0))
                self.dockwidget.push_create.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(1))
                self.dockwidget.push_complete.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(2))
                self.dockwidget.push_next.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(3))
                self.dockwidget.push_next_complete.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(3))
                self.dockwidget.push_cancel_page4.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(3))
                self.dockwidget.push_calcul_page3.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(4))
                self.dockwidget.push_create.clicked.connect(lambda : self.dockwidget.radio_w.setChecked(True))
                self.dockwidget.push_complete.clicked.connect(lambda : self.dockwidget.radio_a.setChecked(True))
                self.dockwidget.push_file.clicked.connect(self.saveFile)
                self.dockwidget.push_file_complete.clicked.connect(self.selectFile)
                self.dockwidget.push_next.clicked.connect(self.setupCorrespondance)
                self.dockwidget.push_next_complete.clicked.connect(self.setupCorrespondance)
                self.dockwidget.push_calcul_page3.clicked.connect(self.setupCalculDistance)
                self.dockwidget.push_add.clicked.connect(self.addToCSV)
                self.dockwidget.push_auto.clicked.connect(self.startAuto)
                self.dockwidget.push_fullauto.clicked.connect(self.startFullAuto)
                self.dockwidget.push_calcul_page4.clicked.connect(self.startDistance)
                self.dockwidget.push_switch.clicked.connect(self.switch)
                self.dockwidget.push_clear.clicked.connect(lambda : self.clearCSV(self.path_csv))
                self.dockwidget.push_zoom_source.clicked.connect(self.zoomSource)

                #Connect lineEdit
                self.dockwidget.lineEdit_file_complete.textChanged.connect(self.fillPreviewWithFile)
                self.dockwidget.lineEdit_buffer_distance.textChanged.connect(self.checkWorkerAuto)
                self.dockwidget.lineEdit_fields_source.textChanged.connect(self.checkWorkerAuto)
                self.dockwidget.lineEdit_precision.textChanged.connect(self.checkWorkerAuto)
                self.dockwidget.lineEdit_buffer_distance.textChanged.connect(self.checkWorkerFullAuto)
                self.dockwidget.lineEdit_precision.textChanged.connect(self.checkWorkerFullAuto)
                self.dockwidget.lineEdit_fields_source.textChanged.connect(self.checkAddButton)
                self.dockwidget.lineEdit_fields_dest.textChanged.connect(self.checkAddButton)
                self.dockwidget.lineEdit_fields_source.editingFinished.connect(self.showCorrespondance)
                self.dockwidget.lineEdit_database.textChanged.connect(self.checkCalculDistance)
                self.dockwidget.lineEdit_host.textChanged.connect(self.checkCalculDistance)
                self.dockwidget.lineEdit_user.textChanged.connect(self.checkCalculDistance)
                self.dockwidget.lineEdit_password.textChanged.connect(self.checkCalculDistance)
                self.dockwidget.lineEdit_port.textChanged.connect(self.checkCalculDistance)

                #Connect checkbox
                self.dockwidget.checkBox_labeling_source.stateChanged.connect(lambda : self.showLabeling(self.layer_source))
                self.dockwidget.checkBox_labeling_dest.stateChanged.connect(lambda : self.showLabeling(self.layer_dest))
                self.dockwidget.checkBox_labeling_statement.stateChanged.connect(lambda : self.showLabeling(QgsLayer.findLayerByName(LAYER_STATEMENT_NAME)))
                self.dockwidget.checkBox_regenerate.stateChanged.connect(lambda : self.dockwidget.listWidget_fields_source.setEnabled(self.dockwidget.checkBox_regenerate.isChecked()))
                self.dockwidget.checkBox_regenerate.stateChanged.connect(lambda : self.dockwidget.listWidget_fields_dest.setEnabled(self.dockwidget.checkBox_regenerate.isChecked()))

                #ListWidget
                self.dockwidget.listWidget_fields_source.itemSelectionChanged.connect(self.checkCalculDistance)
                self.dockwidget.listWidget_fields_dest.itemSelectionChanged.connect(self.checkCalculDistance)


                self.iface.mapCanvas().selectionChanged.connect(self.getSelectedEntity)

            #Set up the first page
            self.dockwidget.stackedWidget.setCurrentIndex(0)

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
