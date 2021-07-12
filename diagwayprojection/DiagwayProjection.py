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
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QProgressBar
from qgis.core import QgsVectorFileWriter, QgsWkbTypes, QgsMapLayerProxyModel, QgsVectorLayer, QgsProject, QgsRuleBasedRenderer, QgsSymbol
from qgis import processing
from os import path, mkdir
import shutil

import time
# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the DockWidget
from .DiagwayProjection_dockwidget import DiagwayProjectionDockWidget
import os.path



def supprDouble(list):
    resList = []
    for element in list:
        if element not in resList:
            resList.append(element)
    return resList


def createDir(dir_path):
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path)
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))
    try:
        mkdir(dir_path)
    except FileExistsError:
        print("Directory already exists")


def bufferLayer(layer, buffer_distance, buffer_path):
    source_layer_feats = layer.getFeatures()
    source_layer_fields = layer.fields()
    writer = QgsVectorFileWriter(buffer_path, 'UTF-8',  source_layer_fields, QgsWkbTypes.Polygon, layer.sourceCrs(), 'ESRI Shapefile')
    for feat in source_layer_feats:
        geom = feat.geometry()
        buffer = geom.buffer(buffer_distance, 5)
        feat.setGeometry(buffer)
        writer.addFeature(feat)
    del(writer)


def changeLayerStyleByRules(source_layer, rules):
    symbol = QgsSymbol.defaultSymbol(source_layer.geometryType())
    symbol.setWidth(0.8)
    renderer = QgsRuleBasedRenderer(symbol)
    root_rule = renderer.rootRule()
    for label, expression, color_name in rules:
        rule = root_rule.children()[0].clone()
        rule.setLabel(label)
        rule.setFilterExpression(expression)
        rule.symbol().setColor(QColor(color_name))
        root_rule.appendChild(rule)
    root_rule.removeChildAt(0)
    source_layer.setRenderer(renderer)


def changeLayerStyleByCSV(source_layer, destination_layer, csv_layer):
    fields_list = []
    csv_fields = csv_layer.fields()
    csv_feats = csv_layer.getFeatures()
    for f in csv_fields:
        fields_list.append(f.name())

    layers_list = [source_layer, destination_layer]
    layers_list_length = len(layers_list)

    for i in range(layers_list_length):
        feats = []
        for f in csv_feats:
            feats.append(f[fields_list[i]])

        txt = ""
        if ((len(feats) > 0) and (type(feats[0]) is str)):
            for f in feats:
                txt += "'{}',".format(f.replace(";", "','"))
        else:
            for f in feats:
                txt += "{},".format(f.replace(";", ","))
        txt = txt[:-1]

        expression = "\"{}\" in ({})".format(fields_list[i], txt)

        rules = (
            ("Road done", expression, "green"),
            ("Road not done", "ELSE", "red")
        )

        changeLayerStyleByRules(layers_list[i], rules)
        csv_feats = csv_layer.getFeatures()


def zoomLayer(self, layer):
    canvas = self.iface.mapCanvas()
    canvas.setExtent(layer.extent())


def getNameFromPath(path):
    name = path.split("/")
    name = name[len(name)-1]
    return name.split(".")[0]


def refreshLayerByPath(path):
    csv_layer_name = getNameFromPath(path)
    csv_layer = QgsProject.instance().mapLayersByName(csv_layer_name)[0]
    csv_layer.setDataSource(path, csv_layer_name, "ogr")


def expressionFromFields(label, line):
    if (type(line.split(";")[0]) is str):
        line = "'" + line.replace(";", "','") + "'"
    else:
        line = line.replace(";", "','")

    return "\"{}\" in ({})".format(label, line)


def removeLayersByName(name):
    project = QgsProject.instance()
    layers = project.mapLayersByName(name)
    for l in layers:
        project.removeMapLayer(l.id())


def cloneAddLayer(layer, name):
    layer_clone = layer.clone()
    layer_clone.setName(name)
    removeLayersByName(name)
    QgsProject.instance().addMapLayer(layer_clone)


def setVisibilityLayerByName(name, visibility):
    project = QgsProject.instance()
    layer = project.mapLayersByName(name)[0]
    project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(visibility)


def setVisibilityLayers(visibility, *layers):
    project = QgsProject.instance()
    for l in layers:
        project.layerTreeRoot().findLayer(l.id()).setItemVisibilityChecked(visibility)
    

def isLT93(layer):
    return layer.crs().authid() == "EPSG:2154"


def findLayerByName(name):
    return QgsProject.instance().mapLayersByName(name)[0]


class DiagwayProjection:
    def __init__(self, iface):
        """Constructor.
        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
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


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('DiagwayProjection', message)


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
        """Add a toolbar icon to the toolbar.

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


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/DiagwayProjection/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'DiagwayProjection'),
            callback=self.run,
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING DiagwayProjection"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD DiagwayProjection"

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&DiagwayProjection'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------

    #Create the path for the CSV file
    def saveFile(self):
        filename, _filter = QFileDialog.getSaveFileName(self.dockwidget, "Select output file ","", '*.csv')
        self.dockwidget.lineEdit_file.setText(filename)


    def selectFile(self):
        filename, _filter = QFileDialog.getOpenFileName(self.dockwidget, "Select output file ","", '*.csv')
        self.dockwidget.lineEdit_file_complete.setText(filename)


    #Filled the combo box fields
    def fillFields(self, comboBox):
        comboBox.clear()
        layer = self.dockwidget.sender().currentLayer()
        fields = layer.fields()
        for f in fields:
            comboBox.addItem(f.name())


    #Check if layer have lambert93 projection
    def isLayerLambert93(self):
        source_layer = self.dockwidget.source_comboBox_layers.currentLayer()
        destination_layer = self.dockwidget.destination_comboBox_layers.currentLayer()
        if ((source_layer != None) and isLT93(source_layer)):
            self.dockwidget.source_img_warning.setHidden(False)
        if ((destination_layer != None) and isLT93(destination_layer)):
            self.dockwidget.destination_img_warning.setHidden(False)


    #Check if all box are correct
    def checkAllCreate(self):
        source_layer = self.dockwidget.source_comboBox_layers.currentLayer()
        destination_layer = self.dockwidget.destination_comboBox_layers.currentLayer()
        outputFile = self.dockwidget.lineEdit_file.text()

        check = ((source_layer != destination_layer) and (source_layer != None) and (destination_layer != None) and (outputFile != "") and isLT93(source_layer) and isLT93(destination_layer))
        self.dockwidget.push_next.setEnabled(check)


    def checkAllComplete(self):
        source_layer = self.dockwidget.source_comboBox_layers_complete.currentLayer()
        destination_layer = self.dockwidget.destination_comboBox_layers_complete.currentLayer()
        outputFile = self.dockwidget.lineEdit_file_complete.text()

        check = ((source_layer != destination_layer) and (source_layer != None) and (destination_layer != None) and (outputFile != "") and isLT93(source_layer) and isLT93(destination_layer))
        self.dockwidget.push_next_complete.setEnabled(check)


    def filePreview(self):
        filename = self.dockwidget.lineEdit_file_complete.text()
        try:
            with open(filename, "r") as csv:
                text = csv.read()
        except (FileNotFoundError, OSError):
            text = "File doesn't exist"
            self.dockwidget.push_next_complete.setEnabled(False)
        except UnicodeDecodeError :
            text = "Unicode error"
            self.dockwidget.push_next_complete.setEnabled(False)
        finally:
            self.dockwidget.textEdit_preview.setText(text)


    def setupPage3(self):
        if (self.dockwidget.radio_w.isChecked()):
            source_field = self.dockwidget.source_comboBox_fields.currentText()
            destination_field = self.dockwidget.destination_comboBox_fields.currentText()
            filename = self.dockwidget.lineEdit_file.text()

            self.dockwidget.source_label_field.setText(source_field + " :")
            self.dockwidget.destination_label_field.setText(destination_field + " :")

            line = "{};{}\n".format(source_field, destination_field)
            with open(filename, "w") as csv:
                csv.write(line)

            source_layer = self.dockwidget.source_comboBox_layers.currentLayer()
            destination_layer = self.dockwidget.destination_comboBox_layers.currentLayer()
        else:
            filename = self.dockwidget.lineEdit_file_complete.text()
            with open(filename, "r") as csv:
                header = csv.readline()

            header = header.split(";")
            source_label = header[0] + " :"
            destination_label = header[1]
            destination_label = destination_label[:-1] + " :"

            self.dockwidget.source_label_field.setText(source_label)
            self.dockwidget.destination_label_field.setText(destination_label)

            source_layer = self.dockwidget.source_comboBox_layers_complete.currentLayer()
            destination_layer = self.dockwidget.destination_comboBox_layers_complete.currentLayer()

        name = getNameFromPath(filename)
        removeLayersByName(name)
        self.iface.addVectorLayer(filename, "", "ogr")

        cloneAddLayer(source_layer, "Statement_source")
        cloneAddLayer(destination_layer, "Statement_destination")

        sourceStatement_layer = findLayerByName("Statement_source")
        destinationStatement_layer = findLayerByName("Statement_destination")
        csv_layer = QgsVectorLayer(filename, "", "ogr")

        setVisibilityLayers(False, source_layer, destination_layer)
        changeLayerStyleByCSV(sourceStatement_layer, destinationStatement_layer, csv_layer)
        zoomLayer(self, sourceStatement_layer)
            

    def checkAutoButton(self):
        txt = self.dockwidget.sender().toPlainText()
        if (txt == ""):
            self.dockwidget.push_auto.setEnabled(False)
        else :
            self.dockwidget.push_auto.setEnabled(True)


    def checkAddButton(self):
        source_textEdit = self.dockwidget.source_textEdit_fields.toPlainText()
        destination_textEdit = self.dockwidget.destination_textEdit_fields.toPlainText()

        if ((destination_textEdit == "") or (source_textEdit == "")):
            self.dockwidget.push_add.setEnabled(False)
        else:
            self.dockwidget.push_add.setEnabled(True)


    def getSelectedEntity(self):
        if (self.dockwidget.radio_a.isChecked()):
            source_layer = self.dockwidget.source_comboBox_layers_complete.currentLayer()
            destination_layer = self.dockwidget.destination_comboBox_layers_complete.currentLayer()
        else:
            source_layer = self.dockwidget.source_comboBox_layers.currentLayer()
            destination_layer = self.dockwidget.destination_comboBox_layers.currentLayer()

        source_fields = ""
        destination_fields = ""

        if (source_layer is not None):
            source_label = self.dockwidget.source_label_field.text()[:-2]
            source_feats = source_layer.selectedFeatures()
            for f in source_feats:
                source_fields += str(f[source_label]) + ";"

        if (destination_layer is not None):
            destination_label = self.dockwidget.destination_label_field.text()[:-2]
            destination_feats = destination_layer.selectedFeatures()
            for f in destination_feats:
                destination_fields += str(f[destination_label]) + ";"

        source_fields = source_fields[:-1]
        destination_fields = destination_fields[:-1]

        if (source_fields != ""):
            self.dockwidget.source_textEdit_fields.setText(source_fields)
        self.dockwidget.destination_textEdit_fields.setText(destination_fields)       


    def addFields(self):
        if (self.dockwidget.radio_a.isChecked()):
            filename = self.dockwidget.lineEdit_file_complete.text()
            source_layer = self.dockwidget.source_comboBox_layers_complete.currentLayer()
            destination_layer = self.dockwidget.destination_comboBox_layers_complete.currentLayer()
        else:
            filename = self.dockwidget.lineEdit_file.text()
            source_layer = self.dockwidget.source_comboBox_layers.currentLayer()
            destination_layer = self.dockwidget.destination_comboBox_layers.currentLayer()

        text_source = self.dockwidget.source_textEdit_fields.toPlainText()
        text_destination = self.dockwidget.destination_textEdit_fields.toPlainText()

        line = "\"{}\";\"{}\"\n".format(text_source, text_destination)
        with open(filename, "a") as csv:
            csv.write(line)

        self.dockwidget.source_textEdit_fields.setText("")
        self.dockwidget.destination_textEdit_fields.setText("")

        refreshLayerByPath(filename)

        project =  QgsProject.instance()
        statementSource_layer = project.mapLayersByName("Statement_source")[0]
        statementDestination_layer = project.mapLayersByName("Statement_destination")[0]

        name_filename = getNameFromPath(filename)
        csv_layer = project.mapLayersByName(name_filename)[0]
        changeLayerStyleByCSV(statementSource_layer, statementDestination_layer, csv_layer)

        setVisibilityLayers(True, statementSource_layer, statementDestination_layer)
        setVisibilityLayers(False, source_layer, destination_layer)

        zoomLayer(self, statementSource_layer)


    def getAutoDestinationFields(self):
        #Create folder in temp
        dir_path = "C:/temp/diagwayProjectionTmpLayer"
        createDir(dir_path)

        #Get data
        if (self.dockwidget.radio_a.isChecked()):
            source_layer = self.dockwidget.source_comboBox_layers_complete.currentLayer()
            destination_layer = self.dockwidget.destination_comboBox_layers_complete.currentLayer()
        else:
            source_layer = self.dockwidget.source_comboBox_layers.currentLayer()
            destination_layer = self.dockwidget.destination_comboBox_layers.currentLayer()
        source_label = self.dockwidget.source_label_field.text()[:-2]
        destination_label = self.dockwidget.destination_label_field.text()[:-2]
        line = ""
        i = 0

        #Count number of source
        source_text = self.dockwidget.source_textEdit_fields.toPlainText()
        source_list = source_text.split(";")
        nbSource = len(source_list)

        #Initialization of the progress bar
        progressMessageBar = self.iface.messageBar().createMessage("Running...")
        progress = QProgressBar()
        progress.setMaximum(nbSource)
        progress.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        progressMessageBar.layout().addWidget(progress)
        self.iface.messageBar().pushWidget(progressMessageBar)

        for source in source_list:
            if (type(source) is str):
                expression = "\"{}\" = '{}'".format(source_label, source)
            else:
                expression = "\"{}\" = {}".format(source_label, source)
            source = str(source)
            source = source.replace("/", "")
            buffer_path = "C:/temp/diagwayProjectionTmpLayer/routeBuffer_" + source + ".shp"
            extract_path = "C:/temp/diagwayProjectionTmpLayer/routeExtract_" + source +".shp"
            dissolve_path = "C:/temp/diagwayProjectionTmpLayer/routeDissolve_" + source +".shp"

            if not source_layer.setSubsetString(expression):
                self.iface.messageBar().clearWidgets()
                self.iface.messageBar().pushMessage("Error", "Source field value is incorrect", level=2, duration=4)
                return 1

            #Graduate buffer
            isEmpty = True
            buffer_distance = 20
            k = 0    
            while (isEmpty and buffer_distance <= 50):
                bufferLayer(source_layer, buffer_distance, buffer_path)

                #Check length of buffer
                buffer_layer = QgsVectorLayer(buffer_path, "", "ogr")
                buffer_layer_feats = buffer_layer.getFeatures()
                count = 0
                for feat in buffer_layer_feats:
                    count += 1

                #We need to dissolve buffer if there are more than one features
                if (count > 1):
                    #Dissolve
                    processing.run('qgis:dissolve', {'INPUT' : buffer_path, 'FIELD' : "stc_route_sta_id", 'OUTPUT' : dissolve_path})
                    #Spatial extract
                    processing.run("qgis:extractbylocation", {'INPUT' : destination_layer, 'PREDICATE' : 6, 'INTERSECT' : dissolve_path, 'OUTPUT' : extract_path})
                else:
                    #Spatial extract
                    processing.run("qgis:extractbylocation", {'INPUT' : destination_layer, 'PREDICATE' : 6, 'INTERSECT' : buffer_path, 'OUTPUT' : extract_path})

                #Get destinations
                res_layer = QgsVectorLayer(extract_path, "res", 'ogr')
                res_layer_feats = res_layer.getFeatures()
                destination_fields = []
                for feat in res_layer_feats:
                    destination_fields.append(feat[destination_label])
                destination_fields_length = len(destination_fields)
                if (destination_fields_length == 0):
                        isEmpty = True
                        buffer_distance += 10
                else:
                    isEmpty = False

                #Rename vector
                if (isEmpty):
                    k += 1
                    buffer_path ="C:/temp/diagwayProjectionTmpLayer/routeBuffer_" + source + "_" + str(k) + ".shp"
                    extract_path = "C:/temp/diagwayProjectionTmpLayer/routeExtract_" + source + "_" + str(k) +".shp"
                    dissolve_path = "C:/temp/diagwayProjectionTmpLayer/routeDissolve_" + source + "_" + str(k) +".shp"

            #Create the line
            for field in destination_fields:
                line += str(field) + ";"

            #Forward the progress bar
            progress.setValue(i + 1)
            i += 1

        #Write line
        line = line[:-1]
        self.dockwidget.destination_textEdit_fields.setText(line)

        #Filter
        destination_expression = expressionFromFields(destination_label, line)
        source_expression = expressionFromFields(source_label, source_text)

        #Change style
        destination_rules = (
            ("Destinations", destination_expression, "blue"),
            ("Other", "ELSE", "brown")
        )
        source_rules = (
            ("source", source_expression, "yellow"),
            ("Other", "ELSE", "brown")
        )

        changeLayerStyleByRules(destination_layer, destination_rules)
        changeLayerStyleByRules(source_layer, source_rules)

        #Zoom
        destination_layer.setSubsetString(destination_expression)
        zoomLayer(self, destination_layer)

        #Hide statement
        setVisibilityLayerByName("Statement_source", False)
        setVisibilityLayerByName("Statement_destination", False)
        setVisibilityLayers(True, source_layer, destination_layer)


        #Clear message
        self.iface.messageBar().clearWidgets()
        if (isEmpty):
            source_layer.setSubsetString(source_expression)
            zoomLayer(self, source_layer)
            self.iface.messageBar().pushMessage("Done", "No destination found", level=1, duration=4)
        else:
            destination_layer.setSubsetString(destination_expression)
            zoomLayer(self, destination_layer)
            self.iface.messageBar().pushMessage("Done", "Destination found !", level=3, duration=4)

        #Clear filter 
        source_layer.setSubsetString("")
        destination_layer.setSubsetString("")

        return 0


    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING DiagwayProjection"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = DiagwayProjectionDockWidget()

                #Reset index layer
                self.dockwidget.source_comboBox_layers.setCurrentIndex(-1)
                self.dockwidget.destination_comboBox_layers.setCurrentIndex(-1)
                self.dockwidget.source_comboBox_layers_complete.setCurrentIndex(-1)
                self.dockwidget.destination_comboBox_layers_complete.setCurrentIndex(-1)

                #Filter for vector layer
                self.dockwidget.source_comboBox_layers.setFilters(QgsMapLayerProxyModel.VectorLayer)
                self.dockwidget.destination_comboBox_layers.setFilters(QgsMapLayerProxyModel.VectorLayer)
                self.dockwidget.source_comboBox_layers_complete.setFilters(QgsMapLayerProxyModel.VectorLayer)
                self.dockwidget.destination_comboBox_layers_complete.setFilters(QgsMapLayerProxyModel.VectorLayer)

                #Check the projection of layer
                self.dockwidget.source_comboBox_layers.layerChanged.connect(self.isLayerLambert93)
                self.dockwidget.destination_comboBox_layers.layerChanged.connect(self.isLayerLambert93)

                #Hide warning pic
                self.dockwidget.source_img_warning.setHidden(False)
                self.dockwidget.destination_img_warning.setHidden(False)

                #Display fields of selected layers
                self.dockwidget.source_comboBox_layers.layerChanged.connect(lambda : self.fillFields(self.dockwidget.source_comboBox_fields))
                self.dockwidget.destination_comboBox_layers.layerChanged.connect(lambda : self.fillFields(self.dockwidget.destination_comboBox_fields))

                #Check before go to next step
                self.dockwidget.source_comboBox_layers.layerChanged.connect(self.checkAllCreate)
                self.dockwidget.destination_comboBox_layers.layerChanged.connect(self.checkAllCreate)
                self.dockwidget.lineEdit_file.textChanged.connect(self.checkAllCreate)
                self.dockwidget.source_comboBox_layers_complete.layerChanged.connect(self.checkAllComplete)
                self.dockwidget.destination_comboBox_layers_complete.layerChanged.connect(self.checkAllComplete)
                self.dockwidget.lineEdit_file_complete.textChanged.connect(self.checkAllComplete)

                #Connect buttons
                self.dockwidget.push_create.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(1))
                self.dockwidget.push_complete.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(2))
                self.dockwidget.push_create.clicked.connect(lambda : self.dockwidget.radio_w.setChecked(True))
                self.dockwidget.push_complete.clicked.connect(lambda : self.dockwidget.radio_a.setChecked(True))
                self.dockwidget.push_next.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(3))
                self.dockwidget.push_next_complete.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(3))
                self.dockwidget.push_cancel_create.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(0))
                self.dockwidget.push_cancel_complete.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(0))
                self.dockwidget.push_cancel_3.clicked.connect(lambda : self.dockwidget.stackedWidget.setCurrentIndex(0))
                self.dockwidget.push_file.clicked.connect(self.saveFile)
                self.dockwidget.push_file_complete.clicked.connect(self.selectFile)
                self.dockwidget.push_next.clicked.connect(self.setupPage3)
                self.dockwidget.push_next_complete.clicked.connect(self.setupPage3)
                self.dockwidget.push_add.clicked.connect(self.addFields)
                self.dockwidget.push_auto.clicked.connect(self.getAutoDestinationFields)

                #Connect textEdit
                self.dockwidget.source_textEdit_fields.textChanged.connect(self.checkAutoButton)
                self.dockwidget.source_textEdit_fields.textChanged.connect(self.checkAddButton)
                self.dockwidget.destination_textEdit_fields.textChanged.connect(self.checkAddButton)

                #Connect lineEdit
                self.dockwidget.lineEdit_file_complete.textChanged.connect(self.filePreview)

                self.iface.mapCanvas().selectionChanged.connect(self.getSelectedEntity)

            #Set up the first page
            self.dockwidget.stackedWidget.setCurrentIndex(0)

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
