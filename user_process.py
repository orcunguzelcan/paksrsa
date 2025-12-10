from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import paks_database
import database_config as dbconfig
data_store = {}
database = paks_database.PaksDatabase(dbconfig.Server, dbconfig.Uid, dbconfig.Password, dbconfig.Database)
def is_valid_tckn(tckn):
    return tckn.isdigit() and len(tckn) == 11

class PaksEnrollServer(BaseHTTPRequestHandler):

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-type", content_type)
        self.end_headers()

    def do_POST(self):
        if self.path != '/enroll':
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not found"}')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            body = json.loads(post_data)
            tckn = body.get('tckn', '')
            fullname = body.get('fullname', '')
            info = body.get('info', '')
            

            if not is_valid_tckn(tckn):
                self._set_headers(400)
                self.wfile.write('{"error": "Geçersiz TCKN"}'.encode('utf-8'))
                return

            if not fullname or len(fullname) > 191:
                self._set_headers(400)
                self.wfile.write('{"error": "Ad Soyad boş olamaz ve 191 karakteri geçemez"}'.encode('utf-8'))
                return
            
            
            person = database.selectPeopleWithTCKN(tckn)
            
            if len(person) <=0 :
                if database.insert_person(fullname,tckn):
                    print("Kişi oluşturma başarılı", fullname,tckn)
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"message": "Kayıt eklenirken bir hata oluştu", "tckn": tckn}).encode())
         
          
            person_id = database.selectPeopleWithTCKN(tckn)[0][0]
            if database.insert_person_fingerprint(person_id, info):
                self._set_headers(200)
                self.wfile.write(json.dumps({"message": "Kayıt eklendi", "tckn": tckn}).encode())
            else:
                self._set_headers(400)
                self.wfile.write(json.dumps({"message": "Kayıt eklenirken bir hata oluştu", "tckn": tckn}).encode())
        
                
                
                
        except Exception as e:
            self._set_headers(400)
            print(e)
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_DELETE(self):
        if self.path != '/enroll':
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not found"}')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        delete_data = self.rfile.read(content_length)
        try:
            body = json.loads(delete_data)
            tckn = body.get('tckn', '')

            if not is_valid_tckn(tckn):
                self._set_headers(400)
                self.wfile.write('{"error": "Geçersiz TCKN"}'.encode('utf-8'))
                return

            if tckn not in data_store:
                self._set_headers(404)
                self.wfile.write('{"error": "TCKN bulunamadı"}'.encode('utf-8'))
                return

            del data_store[tckn]
            self._set_headers(200)
            self.wfile.write(json.dumps({"message": "Kayıt silindi", "tckn": tckn}).encode())

        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode())

def run(server_class=HTTPServer, handler_class=PaksEnrollServer, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Server başlatıldı: http://localhost:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    print("Kayıt servisi başlatılıyor.")
    run()
