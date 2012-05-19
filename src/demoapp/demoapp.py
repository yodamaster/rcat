from tornado import websocket
import tornado.ioloop
import tornado.web
from threading import Thread
from appconnector.proxyconn import ProxyConnector
import logging.config
import json
import data.obm as obm
import data.mysqlconn as MySQLConn
import common.helper as helper

pc = None
datacon = None
appip = None
appport = None

class EchoWebSocket(websocket.WebSocketHandler):
    def open(self):
        global datacon
        logging.debug("App Websocket Open")
        datacon.open_connections('opensim.ics.uci.edu', 'rcat', 'isnotamused', 'rcat')
        result = datacon.execute('SHOW TABLES')
        datacon.create_table("chat","rid")
        datacon.execute("delete from chat")
        print result

    def on_message(self, message):
        try:
            enc = json.loads(message)
            logging.debug(enc["M"])
            
            msg = json.loads(enc["M"])
            user = enc["U"]
            
            newmsg = {}
            if "H" in msg: # Request history from..?
                if "ID" in msg["H"]:
                    history = datacon.select("chat", msg["H"]["ID"])
                    newmsg["M"] = str(history)
                    newmsg["U"] = user
                else:
                    logging.error("[demoapp]: No USERID passed.")
            elif "C" in msg: # Chat
                newmsg["M"] = msg["C"]["M"]
                insert_values = [msg["C"]["ID"],msg["C"]["M"]]
                datacon.insert("chat",insert_values,msg["C"]["ID"])
            json_msg = json.dumps(newmsg)
            self.write_message(json_msg)
        except Exception as e:
            logging.error(e)
            newmsg["M"] = "ERROR"
            if user:
                newmsg["U"] = user
            json_msg = json.dumps(newmsg)
            self.write_message(json_msg)
            return False 
        
        
        # Append metadata here. For now just sending the user and the message.
        """
        newmsg["M"] = msg["M"].swapcase()
        newmsg["U"] = msg["U"]
        json_msg = json.dumps(newmsg)
        datacon.insert("users", [int(newmsg["M"]),0,1,2,3], newmsg["M"])
        datacon.update("users", [("top",3)], newmsg["M"])
        
        """

    def on_close(self):
        logging.debug("App WebSocket closed")
  

handlers = [
    (r"/", EchoWebSocket)
]
      
if __name__ == "__main__":
    appip,appport = helper.parse_input('demoapp.cfg')    
    logging.config.fileConfig("connector_logging.conf")
    logging.debug('[demoapp]: Starting app in ' + appip + appport)
    # TODO: Set options to allow adding OBM as a plugin to the data connector    
    datacon = MySQLConn.MySQLConnector(appip,appport,handlers,{"plugins":["obm"]})

    application = tornado.web.Application(handlers)
    application.listen(appport)
    
    t = Thread(target=tornado.ioloop.IOLoop.instance().start)
    t.daemon = True
    t.start()
    pc = ProxyConnector(["ws://opensim.ics.uci.edu:8888"],"ws://" + appip + ':' + appport)
    helper.terminal()
    
