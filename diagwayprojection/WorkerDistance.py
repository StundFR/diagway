from PyQt5 import QtCore
from .Layer import QgsLayer
from .Tools import *
import traceback
import psycopg2
import csv


SCHEMA = "cores"

class WorkerDistance(QtCore.QObject):
    """Constructor & Variables"""
    finished = QtCore.pyqtSignal(int)
    error = QtCore.pyqtSignal(Exception, str)
    progress = QtCore.pyqtSignal(float)

    def __init__(self, database, host, user, password, regenerate, layer_source, layer_dest, path_csv, field_source, field_dest, fields_source, fields_dest):
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
    #To stop the algorithm
    def kill(self):
        self.killed = True
    #--------------------------------------------------------------------------

    """Run"""
    def run(self):
        try:
            re_geneger = self.regenerate

            self.progress.emit(0)

            addPostgisDB(self.host, self.database, self.user, self.password)

            # Open connection
            conn = psycopg2.connect(host=self.host, dbname=self.database, user=self.user, password=self.password)
            cur = conn.cursor()


            if re_geneger:
                strSqlQuery = "DROP SCHEMA IF EXISTS {} CASCADE".format(SCHEMA)
                cur.execute(strSqlQuery)

                strSqlQuery = "CREATE SCHEMA IF NOT EXISTS {}".format(SCHEMA)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "DROP TABLE IF EXISTS cores.terrain_client"
                cur.execute(strSqlQuery)
                
                strSqlQuery = "CREATE TABLE cores.terrain_client (troncon_id integer,route_client text, cumuld_client numeric,cumulf_client numeric)"
                cur.execute(strSqlQuery)
                
                strSqlQuery = "DROP TABLE IF EXISTS cores.client_terrain"
                cur.execute(strSqlQuery)
                
                strSqlQuery = "CREATE TABLE cores.client_terrain (gid serial,route_client text,type_troncon text,geom_client geometry(LineStringM,2154),point_deb_client geometry(PointM,2154),point_fin_client geometry(PointM,2154),longueur_client numeric,troncon_id integer,cumuld_troncon numeric,cumulf_troncon numeric,longueur_terrain numeric,ecart numeric, sens_ausc integer, a_verifier boolean,CONSTRAINT client_terrain_pkey PRIMARY KEY (gid))"
                cur.execute(strSqlQuery)


                #Importation of QGIS layers in Postgis with selected columns and rename columns 
                self.layer_source.exportToPostgis(self.database, SCHEMA)
                self.layer_dest.exportToPostgis(self.database, SCHEMA)

                sqlQuery = "CREATE TABLE {}.tmp_source AS SELECT * FROM {}.{}".format(SCHEMA, SCHEMA, self.layer_source.name.lower().replace(".", ""))
                cur.execute(sqlQuery)
                
                sqlQuery = "CREATE TABLE {}.tmp_dest AS SELECT * FROM {}.{}".format(SCHEMA, SCHEMA, self.layer_dest.name.lower().replace(".", ""))
                cur.execute(sqlQuery)

                sqlQuery = "DROP TABLE {}.{} CASCADE".format(SCHEMA, self.layer_source.name.lower().replace(".", ""))
                cur.execute(sqlQuery)

                sqlQuery = "DROP TABLE {}.{} CASCADE".format(SCHEMA, self.layer_dest.name.lower().replace(".", ""))
                cur.execute(sqlQuery)

                sqlQuery = "CREATE TABLE {}.stc_voie AS SELECT".format(SCHEMA)
                sqlQuery = addListToStr(sqlQuery, self.fields_source, ",")
                if sqlQuery.find("geom") == -1:
                    sqlQuery += ", geom"
                sqlQuery += " FROM {}.tmp_source".format(SCHEMA)
                sqlQuery = sqlQuery.replace(self.field_source+",", "{} AS sta_id,".format(self.field_source))
                cur.execute(sqlQuery)

                sqlQuery = "CREATE TABLE {}.route_client AS SELECT".format(SCHEMA)
                sqlQuery = addListToStr(sqlQuery, self.fields_dest, ",")
                if sqlQuery.find("geom") == -1:
                    sqlQuery += ", geom"
                sqlQuery += " FROM {}.tmp_dest".format(SCHEMA)
                sqlQuery = sqlQuery.replace(self.field_dest+",", "{} AS route_client,".format(self.field_dest))
                cur.execute(sqlQuery)

                sqlQuery = "DROP TABLE {}.tmp_source CASCADE".format(SCHEMA)
                cur.execute(sqlQuery)

                sqlQuery = "DROP TABLE {}.tmp_dest CASCADE".format(SCHEMA)
                cur.execute(sqlQuery)
                conn.commit()


                strSqlQueryInsertTerrainClient = "INSERT INTO cores.terrain_client (troncon_id,route_client) VALUES(%s,%s)"
                strstrSqlQueryInsertClientTerrain = "INSERT INTO cores.client_terrain (route_client,troncon_id) VALUES(%s,%s)"

                with open(self.path_csv, newline='') as csvfile:
                    reader = csv.DictReader(csvfile,delimiter=';')
                    for row in reader:
                        if self.killed:
                            break
                        sta_id=row[self.field_source]
                        for route_client in (row[self.field_dest]).split(";"):
                            if self.killed:
                                break
                            cur.execute(strSqlQueryInsertTerrainClient,(sta_id,route_client))
                            cur.execute(strstrSqlQueryInsertClientTerrain,(route_client,sta_id))            
                            #print(sta_id,route_client)
                    conn.commit()
                
                strSqlQuery = "UPDATE cores.client_terrain set type_troncon='Route'"
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "UPDATE cores.client_terrain t1 set longueur_client = ST_LENGTH(t2.geom) from cores.route_client t2 where t1.route_client = t2.route_client"
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "Update cores.client_terrain t1 set geom_client = t2.geom from cores.route_client t2 where t1.route_client = t2.route_client"
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "Update cores.client_terrain set point_deb_client = ST_StartPoint(geom_client),point_fin_client = ST_EndPoint(geom_client)"
                cur.execute(strSqlQuery)
                conn.commit()
                
                strSqlQuery ="alter table cores.client_terrain add column geom_terrain geometry(MultiLineStringM,2154)"
                cur.execute(strSqlQuery)

            strSqlQuery ="Update cores.client_terrain t3 set cumuld_troncon = ST_M(ST_LineInterpolatePoint(geom_troncon,ST_LineLocatePoint(geom_troncon,point_deb_client))),  cumulf_troncon = ST_M(ST_LineInterpolatePoint(geom_troncon,ST_LineLocatePoint(geom_troncon,point_fin_client)))      from (    select t1.route_client,t1.geom_client,t1.troncon_id,t2.geom as geom_troncon from cores.client_terrain t1  join cores.stc_voie t2 on t1.troncon_id = t2.sta_id ) r1    where t3.route_client = r1.route_client and t3.troncon_id = r1.troncon_id"
            cur.execute(strSqlQuery)
            conn.commit()

            strSqlQuery ="Update cores.client_terrain set longueur_terrain = abs(cumulf_troncon-cumuld_troncon)"
            cur.execute(strSqlQuery)
            conn.commit()
                            
            strSqlQuery ="Update cores.client_terrain set sens_ausc = CASE When  cumulf_troncon-cumuld_troncon>=0 Then 1 else -1 End"
            cur.execute(strSqlQuery)
            conn.commit()

            strSqlQuery ="Update cores.client_terrain set ecart = (longueur_terrain-longueur_client)"
            cur.execute(strSqlQuery)

            strSqlQuery ="Update cores.client_terrain set a_verifier = CASE WHEN abs(longueur_terrain-longueur_client)>=10 then TRUE ELSE FALSE END"

            cur.execute(strSqlQuery)
            conn.commit()

            strSqlQuery ="Update cores.client_terrain t1 set geom_terrain = ST_LocateBetween(t2.geom,cumuld_troncon,cumulf_troncon) from cores.stc_voie t2 where t1.troncon_id = t2.sta_id"
            cur.execute(strSqlQuery)
            conn.commit()
                    
            conn.close()
            self.progress.emit(100)
            nb = 1
        except Exception as e:
            nb = 0
            self.error.emit(e, traceback.format_exc())
            
        self.finished.emit(nb)
