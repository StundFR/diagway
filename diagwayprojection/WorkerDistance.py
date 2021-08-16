from PyQt5 import QtCore
from .Layer import QgsLayer
from .Tools import *
import traceback
import psycopg2
import csv


SCHEMA = "cores"
SOURCE = "stc_voie"
DEST = "route_client"
FIELD_SOURCE = "sta_id"
FIELD_DEST = "route_client"

class WorkerDistance(QtCore.QObject):
    """Constructor & Variables"""
    finished = QtCore.pyqtSignal(int)
    error = QtCore.pyqtSignal(Exception, str)

    def __init__(self, database, host, user, password, regenerate, layer_source : QgsLayer, layer_dest, path_csv, field_source, field_dest, fields_source, fields_dest):
        QtCore.QObject.__init__(self)
        self.database = database
        self.host = host
        self.user = user
        self.password = password
        self.regenerate = regenerate
        self.layer_source = layer_source
        self.layer_dest = layer_dest
        self.path_csv = path_csv
        self.field_source = field_source
        self.field_dest = field_dest
        self.fields_source = fields_source
        self.fields_dest = fields_dest
        self.killed = False
    #--------------------------------------------------------------------------

    """Function for the algorithm"""
    #--------------------------------------------------------------------------

    """Run"""
    def run(self):
        try:
            self.layer_source.name = self.layer_source.name.lower().replace(".", "")
            self.layer_dest.name = self.layer_dest.name.lower().replace(".", "")

            #Add to database to Qgis
            addPostgisDB(self.host, self.database, self.user, self.password)

            # Open connection
            conn = psycopg2.connect(host=self.host, dbname=self.database, user=self.user, password=self.password)
            cur = conn.cursor()


            if self.regenerate:
                #Creation of all tables we need
                strSqlQuery = "CREATE SCHEMA IF NOT EXISTS {}".format(SCHEMA)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "DROP TABLE IF EXISTS {}.terrain_client".format(SCHEMA)
                cur.execute(strSqlQuery)
                
                strSqlQuery = "CREATE TABLE {}.terrain_client (troncon_id integer,route_client text, cumuld_client numeric,cumulf_client numeric)".format(SCHEMA)
                cur.execute(strSqlQuery)
                
                strSqlQuery = "DROP TABLE IF EXISTS {}.client_terrain".format(SCHEMA)
                cur.execute(strSqlQuery)
                
                strSqlQuery = "CREATE TABLE {}.client_terrain (gid serial,route_client text,type_troncon text,geom_client geometry(LineStringM,2154),point_deb_client geometry(PointM,2154),point_fin_client geometry(PointM,2154),longueur_client numeric,troncon_id integer,cumuld_troncon numeric,cumulf_troncon numeric,longueur_terrain numeric,ecart numeric, sens_ausc integer, a_verifier boolean,CONSTRAINT client_terrain_pkey PRIMARY KEY (gid))".format(SCHEMA)
                cur.execute(strSqlQuery)

                #Importation of QGIS layers in Postgis with selected columns and rename columns 
                self.layer_source.exportToPostgisLineString(self.database, self.host, SCHEMA, SOURCE, "geom")
                self.layer_dest.exportToPostgisLineString(self.database, self.host, SCHEMA, DEST, "geom")

                table_tuple = [(SOURCE, self.fields_source, self.field_source, FIELD_SOURCE), (DEST, self.fields_dest, self.field_dest, FIELD_DEST)]

                for tuple in table_tuple:
                    sqlQuery = "SELECT column_name FROM information_schema.columns WHERE table_schema = '{}' AND table_name = '{}'".format(SCHEMA, tuple[0])
                    cur.execute(sqlQuery)

                    columns = cur.fetchall()
                    for elem in columns:
                        if not elem[0] in tuple[1] and elem[0] != "geom" and elem[0] != tuple[2]: 
                            sqlQuery = "ALTER TABLE {}.{} DROP COLUMN {}".format(SCHEMA, tuple[0], elem[0])
                            cur.execute(sqlQuery)

                    if tuple[2] != tuple[3]:
                        sqlQuery = "ALTER TABLE {}.{} RENAME COLUMN {} TO {}".format(SCHEMA, tuple[0], tuple[2], tuple[3])
                        cur.execute(sqlQuery)

                conn.commit()

                #Insert CSV data in database
                strSqlQueryInsertTerrainClient = "INSERT INTO {}.terrain_client (troncon_id,route_client) VALUES(%s,%s)".format(SCHEMA)
                strstrSqlQueryInsertClientTerrain = "INSERT INTO {}.client_terrain (route_client,troncon_id) VALUES(%s,%s)".format(SCHEMA)

                with open(self.path_csv, newline='') as csvfile:
                    reader = csv.DictReader(csvfile,delimiter=';')
                    reader = csv.DictReader(csvfile,delimiter=';')
                    for row in reader:
                        sta_id=row[self.field_source]
                        for route_client in (row[self.field_dest]).split(";"):
                            cur.execute(strSqlQueryInsertTerrainClient,(sta_id,route_client))
                            cur.execute(strstrSqlQueryInsertClientTerrain,(route_client,sta_id))            
                    conn.commit()
                
                strSqlQuery = "UPDATE {}.client_terrain set type_troncon='Route'".format(SCHEMA)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "UPDATE {}.client_terrain t1 set longueur_client = ST_LENGTH(t2.geom) from {}.{} t2 where t1.route_client = t2.route_client".format(SCHEMA, SCHEMA, DEST)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "Update {}.client_terrain t1 set geom_client = t2.geom from {}.{} t2 where t1.route_client = t2.route_client".format(SCHEMA, SCHEMA, DEST)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "Update {}.client_terrain set point_deb_client = ST_StartPoint(geom_client),point_fin_client = ST_EndPoint(geom_client)".format(SCHEMA)
                cur.execute(strSqlQuery)
                conn.commit()
                
                strSqlQuery = "alter table {}.client_terrain add column geom_terrain geometry(MultiLineStringM,2154)".format(SCHEMA)
                cur.execute(strSqlQuery)

            #Calcul
            strSqlQuery = "Update {}.client_terrain t3 set cumuld_troncon = ST_M(ST_LineInterpolatePoint(geom_troncon,ST_LineLocatePoint(geom_troncon,point_deb_client))), cumulf_troncon = ST_M(ST_LineInterpolatePoint(geom_troncon,ST_LineLocatePoint(geom_troncon,point_fin_client))) from (select t1.route_client,t1.geom_client,t1.troncon_id,t2.geom as geom_troncon from {}.client_terrain t1 join {}.{} t2 on t1.troncon_id = t2.sta_id ) r1 where t3.route_client = r1.route_client and t3.troncon_id = r1.troncon_id".format(SCHEMA, SCHEMA, SCHEMA, SOURCE)
            cur.execute(strSqlQuery)
            conn.commit()

            strSqlQuery = "Update {}.client_terrain set longueur_terrain = abs(cumulf_troncon-cumuld_troncon)".format(SCHEMA)
            cur.execute(strSqlQuery)
            conn.commit()

            strSqlQuery = "Update {}.client_terrain set sens_ausc = CASE When  cumulf_troncon-cumuld_troncon>=0 Then 1 else -1 End".format(SCHEMA)
            cur.execute(strSqlQuery)
            conn.commit()

            strSqlQuery = "Update {}.client_terrain set ecart = (longueur_terrain-longueur_client)".format(SCHEMA)
            cur.execute(strSqlQuery)

            strSqlQuery = "Update {}.client_terrain set a_verifier = CASE WHEN abs(longueur_terrain-longueur_client)>=10 then TRUE ELSE FALSE END".format(SCHEMA)

            cur.execute(strSqlQuery)
            conn.commit()

            strSqlQuery = "Update {}.client_terrain t1 set geom_terrain = ST_LocateBetween(t2.geom, cumuld_troncon, cumulf_troncon) from {}.{} t2 where t1.troncon_id = t2.sta_id AND GeometryType(t2.geom)=' LINESTRING'".format(SCHEMA, SCHEMA, SOURCE)
            cur.execute(strSqlQuery)
            conn.commit()
                    
            conn.close()
            nb = 1
        except Exception as e:
            nb = 0
            self.error.emit(e, traceback.format_exc())
            
        self.finished.emit(nb)
