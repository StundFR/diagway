from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsWkbTypes, QgsProject, QgsRuleBasedRenderer, QgsSymbol
from qgis.PyQt.QtGui import QColor
from qgis import processing


class QgsLayer:
    """Constructor"""
    def __init__(self, path=None, name=None, vectorLayer=None) -> None:
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
        feats = self.vector.getFeatures()
        for feat in feats:
            return type(feat[field_name])

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
        clone = self.vector.clone()
        return QgsLayer(vectorLayer=clone)

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

    def projectionLT93(self, output_path):
        parameters = {'INPUT': self.vector, 'TARGET_CRS': 'EPSG:2154', 'OUTPUT': output_path}
        processing.run("qgis:reprojectlayer", parameters)
        return QgsLayer(output_path, self.name+"_LT93")


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
    def styleByCSV(cls, source_layer, destination_layer, csv_path):
        csv_layer = QgsLayer(csv_path, "")
        fields_list = csv_layer.getFields()
        csv_feats = csv_layer.getFeatures()

        layers_list = [source_layer, destination_layer]
        layers_list_length = len(layers_list)

        for i in range(layers_list_length):
            feats = []
            for feat in csv_feats:
                if (type(feat[fields_list[i]]) is str):
                    split = feat[fields_list[i]].split(";")
                    for elem in split:
                        feats.append(elem)

            field_type = layers_list[i].typeOfField(fields_list[i])

            txt = ""
            if (field_type is str):
                for feat in feats:
                    txt += "'{}',".format(feat)
            else:
                for feat in feats:
                    txt += "{},".format(feat)
            txt = txt[:-1]
            
            expression = "\"{}\" in ({})".format(fields_list[i], txt)

            rules = (
                ("Road done", expression, "green"),
                ("Road not done", "ELSE", "red")
            )

            layers_list[i].styleByRules(rules)
            csv_feats = csv_layer.getFeatures()