from copy import deepcopy
from data.db.mysqlconn import MySQLConnector
from examples.jigsaw.server.mapper.spacepart import SpacePartitioning
from data.plugins.obm import ObjectManager
from random import randint
from rcat import RCAT
from threading import Thread
from tornado import websocket
from tornado.ioloop import IOLoop
from collections import defaultdict
import ConfigParser
import common.helper as helper
import json
import logging.config
import random
import threading
import time
import uuid

global db
global pc
global settings
global datacon
global jigsaw

jigsaw = None
settings = {}
db = None
datacon = None
rcat = None
tables = {}
location = {}
pchandler = None
game_loading = True
coordinator = None

img_settings = {}
board = {}
grid = {}

# default frustum; w and h are determined by each client's canvas size
dfrus = {'x': 0,
         'y':0,
         'scale':1,
         'w': None,
         'h': None
         }

pieces = {}

clientsConnected = 0

class JigsawServerHandler(websocket.WebSocketHandler):
    def open(self):
        global pchandler
        pchandler = self
        logging.debug("Jigsaw App Websocket Open")


    def on_message(self, message):
        JigsawRequestParser(self, message).start()

    def on_close(self):
        logging.debug("App WebSocket closed")

handlers = [
    (r"/", JigsawServerHandler)
]

class JigsawRequestParser(Thread):
    def __init__(self, handler, message):
        Thread.__init__(self)
        self.daemon = True
        self.handler = handler
        self.sched = IOLoop.instance().add_callback
        self.message = message
        self.evt = None
    
    def run(self):
        global clientsConnected
        # TODO: userid and userid[0] is confusing 
        try:
            enc = json.loads(self.message)

            # send the config when the user joins
            if "NU" in enc:
                if enc["SS"] != rcat.pc.adm_id:
                    clientsConnected += 1
                else:
                    # get the user id
                    new_user_list = enc["NU"]
                    if len(new_user_list) != 1:
                        raise Exception('Not supporting multiple new users')
                    new_user = new_user_list[0]

                    # Inform other clients of client connection
                    response = {'M': enc}
                    jsonmsg = json.dumps(response)
                    self.handler.write_message(jsonmsg)
                    clientsConnected += 1
                    datacon.mapper.create_user(new_user)

                    if not game_loading:
                        jigsaw.send_game_to_clients([new_user])
                        
            elif "UD" in enc:
                #User was disconnected. Inform other clients
                clientsConnected -= 1
                if enc["SS"] == rcat.pc.adm_id:
                    datacon.mapper.disconnect_user(enc["UD"])
                    response = {'M': enc}
                    jsonmsg = json.dumps(response)
                    self.handler.write_message(jsonmsg)

            else:
                if game_loading:
                    msg = {'M': {'go':True}}
                    jsonmsg = json.dumps(msg)
                    pchandler.write_message(jsonmsg)
                    return

                # usual message
                logging.debug(enc["M"])
                m = json.loads(enc["M"])
                userid = enc["U"][0]

                if 'rp' in m: # frustum update
                    pf = datacon.mapper.set_user_frustrum(userid, m['rp']['v'])
                    response = {'M': {'pf':pf}, 'U':[userid]}
                    jsonmsg = json.dumps(response)
                    self.handler.write_message(jsonmsg)
                    # TODO: send pieces located in the new frustum

                elif 'usr' in m: # TODO: when does this happen? [tho]
                    update_res = datacon.mapper.new_user_connected(userid, m['usr'])
                    response = {'M': {'scu':update_res}}
                    jsonmsg = json.dumps(response)
                    #self.handler.write_message(jsonmsg) # should not be sent when clients connect [tho]

                elif 'pm' in m: # piece movement
                    pid = m['pm']['id']
                    x = m['pm']['x']
                    y = m['pm']['y']
                    piece = datacon.mapper.select(x, y, pid)

                    lockid = piece['l']
                    if (not lockid or lockid == "None") and not piece['b']: # lock the piece if nobody owns it
                        lockid = userid
                        datacon.mapper.update(x, y, [('l', lockid)], pid)
                        logging.debug('%s starts dragging piece %s' % (userid, pid))
                    #TODO: Better detect conflict. Right now I privilege the latest attempt, not the first.
                    #if lockid == userid: # change location if I'm the owner
                    # update piece coords
                    loc = datacon.mapper.update(x, y, [('x', x), ('y', y)], pid)
                    if loc != "LOCAL":
                        rcat.pc.move_user(userid, loc)
                    # add lock owner to msg to broadcast
                    response = {'M': {'pm': {'id': pid, 'x':x, 'y':y, 'l':lockid}}} #  no 'U' = broadcast
                    # broadcast
                    jsonmsg = json.dumps(response)
                    # TODO: Only send updates to concerned users
                    self.handler.write_message(jsonmsg)
                    #else:
                    #    logging.debug("[jigsawapp]: Weird value for lockid: " + str(lockid))

                elif 'pd' in m: # piece drop
                    pid = m['pd']['id']
                    x = m['pd']['x']
                    y = m['pd']['y']

                    piece = datacon.mapper.select(x, y, pid)

                    if not 'l' in piece:
                        logging.warning("[jigsawapp]: Got something weird: " + str(piece))
                        return
                    lockid = piece['l']
                    if lockid and lockid == userid and not piece['b']: # I was the owner
                        # unlock piece and update piece coords
                        datacon.mapper.update(x, y, [('l', None),('x', x), ('y', y)], pid)

                        # eventually bind piece 
                        bound = m['pd']['b']
                        if bound:# we know the piece is not bound yet
                            logging.debug('%s bound piece %s at %d,%d'
                                      % (userid, pid, x, y))
                            datacon.mapper.update(x, y, [('b', 1)], pid)

                            # Update score board. Separate from 'pd' message because this is always broadcasted.
                            update_res = datacon.mapper.add_to_user_score(userid)
                            response = {'M': {'scu':update_res}}
                            jsonmsg = json.dumps(response)
                            self.handler.write_message(jsonmsg)

                        else:
                            logging.debug('%s dropped piece %s at %d,%d'
                                      % (userid, pid, x, y))
                        # add lock owner to msg to broadcast
                        response = {'M': {'pd': {'id': pid, 'x':x, 'y':y, 'b':bound, 'l':None}}} #  no 'U' = broadcast
                        jsonmsg = json.dumps(response)
                        self.handler.write_message(jsonmsg)
                elif 'ng' in m:
                    pass

                elif 'rg' in m:
                    pass

        except Exception, err:
            logging.exception("[jigsawapp]: Exception in message handling from client:")


class JigsawServer():
    def __init__(self):
        global settings
        # Hooks up to get messages coming in admin channel. 
        # Used to know about new users, servers, and their disconnections.
        rcat.pc.set_admin_handler(self.admin_parser)
        config = helper.open_configuration('jigsaw.cfg')
        settings = self.jigsaw_parser(config)
        helper.close_configuration('jigsaw.cfg')

        user = settings["db"]["user"]
        password = settings["db"]["password"]
        address = settings["db"]["address"]
        database = settings["db"]["db"]

        datacon.db.open_connections(address, user, password, database)
        # DEBUG ONLY: Delete for deployment
        if len(rcat.pc.admins) == 1:
            datacon.mapper.create_table("jigsaw", "pid", True)
            logging.debug("[jigsawapp]: First server up, resetting table..")
            #datacon.db.execute("truncate jigsaw")
        else:
            datacon.mapper.create_table("jigsaw", "pid")

        if settings["main"]["start"] == "true":
            settings["abandon"] = False
            self.start_game()

    def check_game_end(self):
        global settings
        n = -1
        cmd = "select count(*) from " + datacon.mapper.table + " where `b` = 0"
        while (n != 0):
            time.sleep(3)
            res = datacon.db.execute_one(cmd)
            n = int(res['count(*)'])
        scores = datacon.mapper.get_user_scores()
        msg = {'M': {'go':True, 'scores':scores}}
        jsonmsg = json.dumps(msg)
        pchandler.write_message(jsonmsg)
        settings["abandon"] = True 
        
        self.start_game()

    def send_game_to_clients(self,clients=None):
        #TODO: Not send all pieces
        pieces = datacon.mapper.select_all()
        scores = datacon.mapper.get_user_scores()
        
        # send the board config
        cfg = {'img':img_settings,
               'board': board,
               'grid': grid,
               'frus': dfrus,
               'pieces': pieces,
               'clients': clientsConnected,
               'scores' : scores
               }
        if not clients:
            clients = datacon.mapper.user_list()

        for client in clients:
            cfg['myid'] = client
            response = {'M': {'c': cfg}, 'U': [client]}
            jsonmsg = json.dumps(response)
            pchandler.write_message(jsonmsg)


    def jigsaw_parser(self, config):
        app_config = {"main":{"start":"false"}}

        if config:
            try:
                set_main = {}
                set_board = {}
                set_img = {}
                set_grid = {}
                set_db = {}
                for k, v in config.items('Jigsaw_Main'):
                    set_main[k] = v
                app_config["main"] = set_main
                for k, v in config.items('Jigsaw_DB'):
                    set_db[k] = v
                app_config["db"] = set_db
                for k, v in config.items('Jigsaw_Image'):
                    set_img[k] = v
                app_config["img"] = set_img
                for k, v in config.items('Jigsaw_Board'):
                    set_board[k] = float(v)
                app_config["board"] = set_board
                for k, v in config.items('Jigsaw_Grid'):
                    set_grid[k] = int(v)
                app_config["grid"] = set_grid

            except ConfigParser.NoSectionError:
                logging.warn("[jigsawpp]: No Section exception. Might be OK!")
        return app_config

    # Parses messages coming through admin channel of proxy
    def admin_parser(self, msg):
        global game_loading
        global settings
        if "BC" in msg:
            if "NEW" in msg["BC"]:
                global board
                global img_settings
                global grid
                game_loading = True
                
                if "C" in msg["BC"]:
                    global coordinator
                    coordinator = msg["BC"]["C"]
                    logging.info("[jigsawapp]: Coordinator is " + coordinator)

                newgame_settings = msg["BC"]["NEW"]
                board = newgame_settings["board"]
                img_settings = newgame_settings["img"]
                grid = newgame_settings["grid"]
                datacon.mapper.join(newgame_settings)
                if settings["main"]["start"] == "true":
                    logging.info("[jigsawapp]: Starting game, please wait...")                    
                    # Restarting the game at the user's command, or at game over             
                    if settings["abandon"]:
                        logging.info("[jigsawapp]: Abandoning old game.")
                        datacon.mapper.dump_last_game()
                        settings["abandon"] = False

                    count = datacon.db.count("jigsaw")
                    if count > 0:
                            logging.info("[jigsawapp]: Recovering last game.")
                            datacon.mapper.recover_last_game()
                    else:
                        # Prepares the pieces in the database
                        for r in range(grid['nrows']):
                            for  c in range(grid['ncols']):
                                pid = str(uuid.uuid4()) # piece id
                                b = 0 # bound == correctly placed, can't be moved anymore
                                l = None # lock = id of the player moving the piece
                                x = randint(0, board['w'] - grid['cellw'])
                                y = randint(0, board['h'] - grid['cellh'])
                                # Remove h later on!
                                values = [pid, b, x, y, c, r, l]
    
                                datacon.mapper.insert(values, pid)                        
                
                        
                    # Game end checker
                    t = Thread(target=self.check_game_end)
                    t.daemon = True
                    t.start()
                    logging.info("[jigsawapp]: Game has loaded. Have fun!")
                    
                    # Tell servers that new game started
                    newmsg = {"BC":{"LOADED":True}}
                    json_message = json.dumps(newmsg)
                    proxy_admin = random.choice(rcat.pc.admin_proxy.keys())
                    proxy_admin.send(json_message)
                    
                    # Tell clients about new game
                    self.send_game_to_clients()
                    
                    
            elif "LOADED" in msg["BC"]:
                game_loading = False

    def start_game(self):
        global settings
        # Tells all other servers to start game and gives a fixed list of admins so that they all create the same Data Structure
        mod_settings = deepcopy(settings)
        del mod_settings["main"]["start"]
        mod_settings["ADMS"] = list(rcat.pc.admins)
        newmsg = {"BC":{"NEW":mod_settings, "C":rcat.pc.adm_id}}
        json_message = json.dumps(newmsg)
        proxy_admin = random.choice(rcat.pc.admin_proxy.keys())
        proxy_admin.send(json_message)


if __name__ == "__main__":
    logging.config.fileConfig("connector_logging.conf")
    rcat = RCAT(JigsawServerHandler, MySQLConnector, SpacePartitioning, ObjectManager)
    datacon = rcat.datacon
    logging.debug('[jigsawapp]: Starting jigsaw..')

    time.sleep(2)

    jigsaw = JigsawServer()
    helper.terminal()
