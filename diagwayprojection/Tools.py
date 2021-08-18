from qgis import processing
from qgis.core import QgsVectorFileWriter, QgsProject
from os import mkdir, path
import shutil
import tempfile

from .Layer import QgsLayer
from PyQt5.QtCore import QSettings

LAYER_STATEMENT_NAME = "Statement_source"
DIR_NAME = "diagwayProjectionTmpLayer"

#Delete duplicate value in list
def supprDouble(list):
    resList = []
    for element in list:
        if element not in resList:
            resList.append(element)
    return resList

#Create a directory 
def createDir(path_dir):
    try:
        mkdir(path_dir)
    except FileExistsError:
        #print("Directory already exists")
        pass

#Remove a directory
def removeDir(path_dir):
    try:
        shutil.rmtree(path_dir)
    except OSError as e:
        print("Error: %s - %s." % (e.filename, e.strerror))

#Get the name of file from his path
def getNameFromPath(path):
    name = path.split("/")
    name = name[len(name)-1]
    return name.split(".")[0]

#Generate an expression for filter layer
def expressionFromFields(label, line):
    if (type(line.split(";")[0]) is str):
        line = "'" + line.replace(";", "','") + "'"
    else:
        line = line.replace(";", "','")

    return "\"{}\" in ({})".format(label, line)

#Find the line of duplicate value in CSV file
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

#Remove a line from a csv file
def removeLineFile(path_file, nLine):
    with open(path_file, "r") as file:
        file_lines = file.readlines()
    
    i = 1
    with open(path_file, "w") as file:
        for line in file_lines:
            if (i != nLine):
                file.write(line)
            i += 1

#Extract by location proccesing, parameters : contains
def extractByLocation(layer_source, layer_dest, path_output):
    if (not path.isfile(path_output)):
        parameters = {'INPUT' : layer_source.vector, 'PREDICATE' : 6, 'INTERSECT' : layer_dest.vector, 'OUTPUT' : path_output}
        processing.run("qgis:extractbylocation", parameters)

#Calcul projection for source layer
def getDestBySource(layer_source, layer_dest, source_value, field_source, field_dest, buffer_distance, precision):
    #Create folder in temp
    path_dir = getPath()

    source = str(source_value).replace("/", "")
    path_buffer = "{}/buffer_BD{}_LS{}_FS{}_SV{}.shp".format(path_dir, buffer_distance, layer_source.name.replace(".", ""), field_source, source)
    path_intersect = "{}/intersect_EPS{}_BD{}_LS{}_FS{}_SV{}_LD{}_FD{}.shp".format(path_dir, precision, buffer_distance, layer_source.name.replace(".", ""), field_source, source, layer_dest.name.replace(".", ""), field_dest)

    if (type(source_value) is str):
        expression = "\"{}\" = '{}'".format(field_source, source_value)
    else:
        expression = "\"{}\" = {}".format(field_source, source_value)

    if not layer_source.filter(expression):
        return []

    layer_buffer = layer_source.buffer(buffer_distance, path_buffer)

    layer_res = intersect(layer_dest, layer_buffer, precision, path_intersect)

    #Get destinations
    layer_res_feats = layer_res.getFeatures()
    dest_values = []
    for feat in layer_res_feats:
        dest_values.append(str(feat[field_dest]))

    return dest_values

#Calcul if destination layer is the projection for source layer
def getDestByDest(layer_source, layer_dest, source_value, field_source, field_dest, buffer_distance, precision, value_already_done):
    path_dir = getPath()

    source = str(source_value).replace("/", "")
    path_buffer = "{}/buffer_BD{}_LS{}_FS{}_SV{}.shp".format(path_dir, buffer_distance, layer_source.name.replace(".", ""), field_source, source)
    layer_buffer_source = layer_source.buffer(buffer_distance, path_buffer)

    path_clip = "{}/clip_LS{}_LD{}.shp".format(path_dir, layer_dest.name.replace(".", ""), getNameFromPath(path_buffer))
    clip(layer_dest, layer_buffer_source, path_clip)
    layer_extract = QgsLayer(path_clip, getNameFromPath(path_clip))

    field_values = []
    layer_extract_feats = layer_extract.getFeatures()
    for feat in layer_extract_feats:
        field_values.append(str(feat[field_dest]))


    dest_values = []
    for value in field_values:
        if (str(value) not in value_already_done):
            res_value = getDestBySource(layer_dest, layer_source, value, field_dest, field_source, buffer_distance, precision)
            if (source_value in res_value):
                dest_values.append(value)

    return dest_values

#Project source layer on destination layer
def projection(layer_source, layer_dest, source_value, field_source, field_dest, buffer_distance, precision):
    dest_values = getDestBySource(layer_source, layer_dest, source_value, field_source, field_dest, buffer_distance, precision)
    dest_values += getDestByDest(layer_source, layer_dest, source_value, field_source, field_dest, buffer_distance, precision, dest_values)
    layer_source.filter("")
    layer_dest.filter("")

    return supprDouble(dest_values)

#Sort features by their position, West to east
def sortFeaturesByGeom(layer, values, field):
    feats = layer.getFeaturesOrderByField("geom", True)
    res = []
    
    for feat in feats:
        try:
            value = feat[field]
        except KeyError:
            value = feat[field[:-2]]
        if  value in values:
            res.append(value)

    return res
    
#Add line in CSV file
def addLineCSV(csv_path, source_value, destination_value):
    duplicateLine = duplicateLineCSV(csv_path, source_value)

    if (duplicateLine != 0):
        removeLineFile(csv_path, duplicateLine)

    line = "{};\"{}\"\n".format(source_value, destination_value)
    with open(csv_path, "a") as csv:
        csv.write(line)

#Create rules style for layer based on CSV file
def createLayerStyleByCSV(csv_path):
    csv_layer = QgsLayer(csv_path, "")
    csv_layer.refresh()

    layer_statement = QgsLayer.findLayerByName(LAYER_STATEMENT_NAME)

    QgsLayer.styleByCSV(layer_statement, csv_path)

    return layer_statement

#merged list of layers
def mergeLayers(layers, path_output):
    if (not path.isfile(path_output)):
        parameters = {'LAYERS': layers, 'CRS': 'EPSG:4326', 'OUTPUT': path_output}
        processing.run("native:mergevectorlayers", parameters) 

#Difference processing
def difference(layer_source, layer_dest, path_output):
    if (not path.isfile(path_output)):
        parameters = {"INPUT" : layer_source.vector, "OVERLAY" : layer_dest.vector, "OUTPUT" : path_output}
        processing.run("qgis:difference", parameters)

#Clip processing
def clip(layer_source, layer_dest, path_output):
    if (not path.isfile(path_output)):
        parameters = {"INPUT" : layer_source.vector, "OVERLAY" : layer_dest.vector, "OUTPUT" : path_output}
        processing.run("qgis:clip", parameters)

#Extract by location, parameters : intersect
def extractByLocationIntersect(layer_source, layer_dest, path_output):
    if (not path.isfile(path_output)):
        parameters = {'INPUT' : layer_source.vector, 'PREDICATE' : 0, 'INTERSECT' : layer_dest.vector, 'OUTPUT' : path_output}
        processing.run("qgis:extractbylocation", parameters)

#Works like extract by location, parameters : contains, with a precision 
def intersect(layer_source, layer_dest, precision, path_output):
    if (path.isfile(path_output)):
        return QgsLayer(path_output, getNameFromPath(path_output))

    path_dir = getPath()

    path_clip = "{}/clip_LS{}_LD{}.shp".format(path_dir, layer_source.name.replace(".", ""), layer_dest.name.replace(".", ""))
    clip(layer_source, layer_dest, path_clip)
    layer_clip = QgsLayer(path_clip, getNameFromPath(path_clip))

    path_extract = "{}/extract_LS{}_LD{}.shp".format(path_dir, layer_source.name.replace(".", ""), layer_dest.name.replace(".", ""))
    extractByLocationIntersect(layer_source, layer_dest, path_extract)
    layer_extract = QgsLayer(path_extract, getNameFromPath(path_extract))

    layer_clip.addLengthFeat()
    layer_extract.addLengthFeat()

    ids = []
    layer_clip_length = layer_clip.getAllFeatures("newLength")
    layer_extract_length = layer_extract.getAllFeatures("newLength")

    for i in range(len(layer_clip_length)):
        if (layer_clip_length[i]/layer_extract_length[i] >= precision):
            ids.append(i)

    layer_extract_feats = layer_extract.getFeatures()

    i = 0
    selection = []
    for feat in layer_extract_feats:
        if (i in ids):
            selection.append(feat)
        i += 1

    layer_extract.vector.selectByIds([s.id() for s in selection])

    writer = QgsVectorFileWriter.writeAsVectorFormat(layer_extract.vector, path_output, "utf-8", layer_extract.vector.sourceCrs(), "ESRI Shapefile", onlySelected=True)
    del(writer)

    return QgsLayer(path_output, getNameFromPath(path_output))

#Get the path of temporary files
def getPath():
    path_temp = tempfile.gettempdir()
    path_dir = "{}/{}_{}".format(path_temp, DIR_NAME, getNameFromPath(QgsProject.instance().readPath("./")))
    createDir(path_dir)
    return path_dir

#Create database in QGIS
def addPostgisDB(host, dbname, user, password, port):
    path = "PostgreSQL/connections/{}/".format(dbname)
    s = QSettings()
    s.setValue(path + "allowGeometrylessTables", False)
    s.setValue(path + "autocfg", "")
    s.setValue(path + "database", dbname)
    s.setValue(path + "dontResolveType", False)
    s.setValue(path + "estimatedMetadata", False)
    s.setValue(path + "geometryColumnsOnly", False)
    s.setValue(path + "host", host)
    s.setValue(path + "password", password)
    s.setValue(path + "port", port)
    s.setValue(path + "projectsInDatabase", False)
    s.setValue(path + "publicOnly", False)
    s.setValue(path + "savePassword", False)
    s.setValue(path + "saveUsername", False)
    s.setValue(path + "service", "")
    s.setValue(path + "sslmode", "SslDisable")
    s.setValue(path + "username", user)


def addListToStr(text, liste, sep):
    for elem in liste:
        text += " {}{}".format(str(elem), str(sep))
    return text[:-1]