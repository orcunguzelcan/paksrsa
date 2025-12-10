from threading import Lock
import datetime
import os


LoggerMutex = Lock()

 
class LOGGER:
    @staticmethod
    def WriteLog(log):
        
        dateTime = datetime.datetime.now()
        LoggerMutex.acquire()
        path = str("logs/" + str(dateTime.year) + "/" + str(dateTime.month) + "/" + str(dateTime.day))
        if not os.path.exists(path):
            os.makedirs(path)
        path += "/program.log"
        nowDateTime = str(dateTime.strftime("%Y-%m-%d (%H:%M:%S)"))

        with open(path, 'a') as file:
            file.write(nowDateTime + " -->  " + str(log) + "\n")

        LoggerMutex.release()
