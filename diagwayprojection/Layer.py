from os import path
from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsWkbTypes, QgsProject, QgsRuleBasedRenderer, QgsSymbol, QgsVectorDataProvider, QgsField, QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,QgsVectorLayerSimpleLabeling, QgsFeatureRequest
from qgis.PyQt.QtGui import QColor, QFont
from qgis import processing
from qgis.core.additions.edit import edit

from PyQt5.QtCore import *
import os.path

LAYER_STATEMENT_NAME = "Statement_source"

class QgsLayer:
    """Constructor"""
    def __init__(self, path=None, name=None, vectorLayer=None):
        if (vectorLayer is None):
            self.path = path
            self.name = name
            self.vector = QgsVectorLayer(path, name, "ogr")
            self.crs = self.vector.crs().authid()
        else:
            self.vector = vectorLayer
            self.name = self.vector.name()
            self.path = self.vector.dataProvider().dataSourceUri().split("|")[0]
            self.crs = self.vector.crs().authid()
            self.id = self.vector.id()


    """Method"""
    #set name of layer
    def setName(self, name):
        self.vector.setName(name)
        self.name = name

    #get fields name of layer
    def getFields(self):
        fields_list = []
        layer_fields = self.vector.fields()
        for f in layer_fields:
            fields_list.append(f.name())
        return fields_list

    #get type of field of layer
    def typeOfField(self, field_name):
        feats = self.getFeatures()
        for feat in feats:
            try:
                res = type(feat[field_name])
            except KeyError:
                res = type("")
            return res

    #zoom on layer
    def zoom(self, dlg):
        canvas = dlg.iface.mapCanvas()
        canvas.setExtent(self.vector.extent())

    #create a buffer for a layer
    def buffer(self, buffer_distance, path_buffer):
        from .Tools import getNameFromPath
        buffer_name = getNameFromPath(path_buffer)

        if (os.path.isfile(path_buffer)):
            return QgsLayer(path_buffer, buffer_name)

        source_layer_feats = self.vector.getFeatures()
        source_layer_fields = self.vector.fields()
        writer = QgsVectorFileWriter(path_buffer, 'UTF-8',  source_layer_fields, QgsWkbTypes.Polygon, self.vector.sourceCrs(), 'ESRI Shapefile')
        for feat in source_layer_feats:
            geom = feat.geometry()
            buffer = geom.buffer(buffer_distance, 5)
            feat.setGeometry(buffer)
            writer.addFeature(feat)
        del(writer)
        return QgsLayer(path_buffer, buffer_name)

    #refresh data of layer
    def refresh(self):
        self.vector.setDataSource(self.path, self.name, "ogr")

    #add layer to tree root
    def add(self):
        layer = QgsProject.instance().addMapLayer(self.vector)
        self.id = layer.id()
        
    #remove layer of tree root
    def remove(self):
        QgsProject.instance().removeMapLayers([self.id])

    #clone layer
    def clone(self):
        name = self.name + "_clone"
        clone_vector = QgsVectorLayer(self.vector.source(), name, self.vector.providerType())
        clone_layer = QgsLayer(vectorLayer=clone_vector)
        return clone_layer

    #set visibility of layer
    def setVisibility(self, visibility):
        QgsProject.instance().layerTreeRoot().findLayer(self.id).setItemVisibilityChecked(visibility)

    #return if layer is visible
    def isVisible(self):
        return QgsProject.instance().layerTreeRoot().findLayer(self.id).isVisible()

    #return true if layer is projected in Lambert-93
    def isLT93(self):
        return (self.crs == "EPSG:2154")

    #filter layer by expression
    def filter(self, expression):
        return self.vector.setSubsetString(expression)

    #get features of layer
    def getFeatures(self):
        return self.vector.getFeatures()

    #get features of layer order by field
    def getFeaturesOrderByField(self, field, ascending):
        request = QgsFeatureRequest()
        clause = QgsFeatureRequest.OrderByClause(field, ascending=ascending)
        orderby = QgsFeatureRequest.OrderBy([clause])
        request.setOrderBy(orderby)
        return self.vector.getFeatures(request)

    #return selected features
    def selectedFeatures(self):
        return self.vector.selectedFeatures()

    #Select features by expression
    def selectByExpression(self, expression):
        return self.vector.selectByExpression(expression)

    #change style of layer by rules
    def styleByRules(self, rules):
        symbol = QgsSymbol.defaultSymbol(self.vector.geometryType())
        symbol.setWidth(0.8)
        renderer = QgsRuleBasedRenderer(symbol)
        root_rule = renderer.rootRule()
        for label, expression, color_name in rules:
            rule = root_rule.children()[0].clone()
            rule.setLabel(label)
            rule.setFilterExpression(expression)
            rule.symbol().setColor(color_name)
            root_rule.appendChild(rule)
        root_rule.removeChildAt(0)
        self.vector.setRenderer(renderer)

    #Set the symbol of a layer
    def setSymbol(self, width, color):
        symbol = QgsSymbol.defaultSymbol(self.vector.geometryType())
        symbol.setWidth(width)
        symbol.setColor(color)
        renderer = QgsRuleBasedRenderer(symbol)
        self.vector.setRenderer(renderer)

    #Add the length of each features of layer
    def addLengthFeat(self):
        self.vector.startEditing()
        caps = self.vector.dataProvider().capabilities()
        features = self.getFeatures()

        if caps & QgsVectorDataProvider.AddAttributes:
            self.vector.dataProvider().addAttributes([QgsField("newLength", QVariant.Double, "Double")])
        self.vector.commitChanges()

        self.vector.startEditing()
        idx = self.vector.fields().indexFromName('newLength')
        for feature in features:
            if caps & QgsVectorDataProvider.ChangeAttributeValues:
                fid = feature.id()
                flen = feature.geometry().length()
                self.vector.changeAttributeValue(fid, idx, flen)
        self.vector.commitChanges()

    #Add an unique ID of each features of layer
    def addUniqueID(self):
        caps = self.vector.dataProvider().capabilities()
        field = QgsField('newID', QVariant.Int, "Int")

        self.vector.startEditing()
        if caps & QgsVectorDataProvider.AddAttributes:
            self.vector.dataProvider().addAttributes([field])
        self.vector.updateFields()

        id = self.vector.dataProvider().fieldNameIndex('newID')
        self.vector.commitChanges()

        count=1
        self.vector.startEditing()
        # fill the field ID with rownumber
        for f in self.vector.getFeatures():
            rownum = count
            count+=1
            f[id]=rownum
            self.vector.updateFeature(f)

        self.vector.commitChanges()

    #Get all the features of a field
    def getAllFeatures(self, field):
        features = self.getFeatures()
        feats = []
        for f in features:
            feats.append(f[field])
        return feats

    #Export layer
    def export(self, path_output):
        writer = QgsVectorFileWriter.writeAsVectorFormat(self.vector, path_output, 'UTF-8', self.vector.sourceCrs(), 'ESRI Shapefile')
        del(writer)

    #Add label
    def labeling(self, fontSize, field, color):
        layer_settings  = QgsPalLayerSettings()
        text_format = QgsTextFormat()

        text_format.setFont(QFont("Arial", fontSize))
        text_format.setSize(fontSize)
        text_format.setColor(QColor(color))

        buffer_settings = QgsTextBufferSettings()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(0.05)
        buffer_settings.setColor(QColor("Black"))

        text_format.setBuffer(buffer_settings)

        layer_settings.setFormat(text_format)

        layer_settings.fieldName = field
        layer_settings.placement = QgsPalLayerSettings.Line

        layer_settings.enabled = True

        layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)
        self.vector.setLabelsEnabled(True)
        self.vector.setLabeling(layer_settings)
        self.vector.triggerRepaint()

    #Display/hide label of a layer
    def setLabel(self, choix):
        self.vector.setLabelsEnabled(choix)
        self.vector.triggerRepaint()

    #Projecto layer to Lambert93
    def projectionLT93(self, path_output):
        if (os.path.isfile(path_output)):
            return QgsLayer(path_output, "{}_LT93".format(self.name))

        parameters = {'INPUT': self.vector, 'TARGET_CRS': 'EPSG:2154', 'OUTPUT': path_output}
        processing.run("qgis:reprojectlayer", parameters)

        return QgsLayer(path_output, self.name+"_LT93")

    #Remove features of a layer by an expression
    def removeFeaturesByExpression(self, expression):
        with edit(self.vector):
            request = QgsFeatureRequest().setFilterExpression(expression)
            request.setSubsetOfAttributes([])
            request.setFlags(QgsFeatureRequest.NoGeometry)
            for f in self.vector.getFeatures(request):
                self.vector.deleteFeature(f.id())

    #Rename field name
    def renameField(self, oldname, newname):
        findex = self.vector.dataProvider().fieldNameIndex(oldname)
        if findex != -1:
            self.vector.dataProvider().renameAttributes({findex: newname})
            self.vector.updateFields()


    def isFieldExist(self, field):
        findex = self.vector.dataProvider().fieldNameIndex(field)
        if findex == -1:
            return False
        else:
            return True

    """class functions"""
    #return layer by his name
    @classmethod
    def findLayerByName(cls, name):
        layer = QgsProject.instance().mapLayersByName(name)[0]
        return QgsLayer(vectorLayer=layer)

    #Remove layer by his name
    @classmethod
    def removeLayersByName(cls, name):
        project = QgsProject.instance()
        layers = project.mapLayersByName(name)
        for l in layers:
            project.removeMapLayers([l.id()])

    #Changes the style of a layer using a CSV file
    @classmethod
    def styleByCSV(cls, source_layer, csv_path):
        csv_layer = QgsLayer(csv_path, "")
        fields_list = csv_layer.getFields()
        csv_feats = csv_layer.getFeatures()
        color = (QColor("green"), QColor("red"))


        feats = []
        for feat in csv_feats:
            if (type(feat[fields_list[0]]) is str):
                split = feat[fields_list[0]].split(";")
                for elem in split:
                    feats.append(elem)

        field_type = source_layer.typeOfField(fields_list[0])

        txt = ""
        if (field_type is str):
            for feat in feats:
                txt += "'{}',".format(feat)
        else:
            for feat in feats:
                txt += "{},".format(feat)
        txt = txt[:-1]
            
        expression = "\"{}\" in ({})".format(fields_list[0], txt)

        rules = (
            ("Done", expression, color[0]),
            ("Not done", "ELSE", color[1])
        )

        source_layer.styleByRules(rules)
        csv_feats = csv_layer.getFeatures()
    