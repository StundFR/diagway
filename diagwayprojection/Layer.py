from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsWkbTypes, QgsProject, QgsRuleBasedRenderer, QgsSymbol, QgsVectorDataProvider, QgsField
from qgis.PyQt.QtGui import QColor
from qgis import processing
from PyQt5.QtCore import *

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
    def buffer(self, buffer_distance, buffer_path):
        source_layer_feats = self.vector.getFeatures()
        source_layer_fields = self.vector.fields()
        buffer_name = "{}_buffer".format(self.name)
        writer = QgsVectorFileWriter(buffer_path, 'UTF-8',  source_layer_fields, QgsWkbTypes.Polygon, self.vector.sourceCrs(), 'ESRI Shapefile')
        for feat in source_layer_feats:
            geom = feat.geometry()
            buffer = geom.buffer(buffer_distance, 5)
            feat.setGeometry(buffer)
            writer.addFeature(feat)
        del(writer)
        return QgsLayer(buffer_path, buffer_name)

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
        clone_vector = self.vector.clone()
        clone_layer = QgsLayer(vectorLayer=clone_vector)
        clone_layer.setName(name)
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

    #return selected features
    def selectedFeatures(self):
        return self.vector.selectedFeatures()

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
            rule.symbol().setColor(QColor(color_name))
            root_rule.appendChild(rule)
        root_rule.removeChildAt(0)
        self.vector.setRenderer(renderer)


    def addLengthFeat(self):
        self.vector.startEditing()
        caps = self.vector.dataProvider().capabilities()
        features = self.getFeatures()

        if caps & QgsVectorDataProvider.AddAttributes:
            self.vector.dataProvider().addAttributes([QgsField("Length", QVariant.Double, "Double")])
        self.vector.commitChanges()

        self.vector.startEditing()
        idx = self.vector.fields().indexFromName('Length')
        for feature in features:
            if caps & QgsVectorDataProvider.ChangeAttributeValues:
                fid = feature.id()
                flen = feature.geometry().length()
                self.vector.changeAttributeValue(fid, idx, flen)
        self.vector.commitChanges()


    def getAllFeatures(self, field):
        features = self.getFeatures()
        feats = []
        for f in features:
            feats.append(f[field])
        return feats


    def export(self, output_path):
        writer = QgsVectorFileWriter.writeAsVectorFormat(self.vector, output_path, 'UTF-8', self.vector.sourceCrs(), 'ESRI Shapefile')
        del(writer)


    """class functions"""
    #return layer by his name
    @classmethod
    def findLayerByName(cls, name):
        layer = QgsProject.instance().mapLayersByName(name)[0]
        return QgsLayer(vectorLayer=layer)

    @classmethod
    def removeLayersByName(cls, name):
        project = QgsProject.instance()
        layers = project.mapLayersByName(name)
        for l in layers:
            project.removeMapLayers([l.id()])

    @classmethod
    def styleByCSV(cls, source_layer, csv_path):
        csv_layer = QgsLayer(csv_path, "")
        fields_list = csv_layer.getFields()
        csv_feats = csv_layer.getFeatures()
        color = ("green", "red")


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