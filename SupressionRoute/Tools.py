from qgis import processing
from os import mkdir
import os.path
import shutil

from .Layer import QgsLayer

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


def getNameFromPath(path):
    name = path.split("/")
    name = name[len(name)-1]
    return name.split(".")[0]


def expressionFromFields(label, line):
    if (type(line.split(";")[0]) is str):
        line = "'" + line.replace(";", "','") + "'"
    else:
        line = line.replace(";", "','")

    return "\"{}\" in ({})".format(label, line)


def duplicateLineCSV(csv_path, source_value):
    i = 0
    with open(csv_path, "r") as csv:
        lines = csv.readlines()
    for line in lines:
        i += 1
        if (line.split(";")[0] == str(source_value)):
            return i
    i = 0
    return i


def removeLineFile(file_path, nLine):
    with open(file_path, "r") as file:
        file_lines = file.readlines()
    
    i = 1
    with open(file_path, "w") as file:
        for line in file_lines:
            if (i != nLine):
                file.write(line)
            i += 1


def extractByLocation(source_layer, destination_layer, output_path):
    parameters = {'INPUT' : source_layer.vector, 'PREDICATE' : 6, 'INTERSECT' : destination_layer.vector, 'OUTPUT' : output_path}
    processing.run("qgis:extractbylocation", parameters)


def getDestBySource(source_layer, destination_layer, source_value, source_field, destination_field, buffer_distance):
    #Create folder in temp
    dir_path = "C:/temp/diagwayProjectionTmpLayer"
    createDir(dir_path)

    source = str(source_value)
    source = source.replace("/", "")
    buffer_path = "C:/temp/diagwayProjectionTmpLayer/routeBuffer_" + source + ".shp"
    extract_path = "C:/temp/diagwayProjectionTmpLayer/routeExtract_" + source +".shp"
    dissolve_path = "C:/temp/diagwayProjectionTmpLayer/routeDissolve_" + source +".shp"

    if (type(source_value) is str):
        expression = "\"{}\" = '{}'".format(source_field, source_value)
    else:
        expression = "\"{}\" = {}".format(source_field, source_value)

    if not source_layer.filter(expression):
        return []

    source_layer.buffer(buffer_distance, buffer_path)

    #Check length of buffer
    buffer_layer = QgsLayer(buffer_path, "")
    buffer_layer_feats = buffer_layer.getFeatures()
    count = 0
    for feat in buffer_layer_feats:
        count += 1

    #We need to dissolve buffer if there are more than one features
    if (count > 1):
        #Dissolve
        processing.run('qgis:dissolve', {'INPUT' : buffer_path, 'FIELD' : "stc_route_sta_id", 'OUTPUT' : dissolve_path})
        #Spatial extract
        processing.run("qgis:extractbylocation", {'INPUT' : destination_layer.vector, 'PREDICATE' : 6, 'INTERSECT' : dissolve_path, 'OUTPUT' : extract_path})
    else:
        #Spatial extract
        processing.run("qgis:extractbylocation", {'INPUT' : destination_layer.vector, 'PREDICATE' : 6, 'INTERSECT' : buffer_path, 'OUTPUT' : extract_path})

    #Get destinations
    res_layer = QgsLayer(extract_path, "res")
    res_layer_feats = res_layer.getFeatures()
    destination_values = []
    for feat in res_layer_feats:
        destination_values.append(feat[destination_field])

    return destination_values
        

def addLineCSV(csv_path, source_value, destination_value):
    duplicateLine = duplicateLineCSV(csv_path, source_value)

    if (duplicateLine != 0):
        removeLineFile(csv_path, duplicateLine)

    line = "{};\"{}\"\n".format(source_value, destination_value)
    with open(csv_path, "a") as csv:
        csv.write(line)


def createLayerStyleByCSV(csv_path):
    csv_layer = QgsLayer(csv_path, "")
    csv_layer.refresh()

    statementSource_layer = QgsLayer.findLayerByName("Statement_source")
    statementDestination_layer = QgsLayer.findLayerByName("Statement_destination")

    QgsLayer.styleByCSV(statementSource_layer, statementDestination_layer, csv_path)
    statementSource_layer.setVisibility(True)
    statementDestination_layer.setVisibility(True)

    return statementSource_layer, statementDestination_layer


def mergeLayers(layers, output_path):
    parameters = {'LAYERS': layers, 'CRS': 'EPSG:4326', 'OUTPUT': output_path}
    processing.run("native:mergevectorlayers", parameters) 


def getAllFeatures(layer, field):
    features = layer.getFeatures()
    feats = []
    for f in features:
        feats.append(f[field])
    return feats


def difference(source_layer, destination_layer):
    extract_feats = []
    source_feats = source_layer.getFeatures()
    destination_feat = destination_layer.getFeatures()
    fields = source_layer.getFields()

    source_values = []
    for source_feat in source_feats:
        for field in fields:
            source_values.append(source_feat[field])

        fields = source_layer.getFields()
        
        for dest_feat in destination_feat:
            dest_values = []
            for field in fields:
                dest_values.append(dest_feat[field])

            fields = source_layer.getFields()

            if (source_values != dest_values):
                extract_feats.append(source_feat)

        destination_feat = destination_layer.getFeatures()

    return extract_feats



