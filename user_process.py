from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import string  # --- EKLENDİ: Hex kontrolü için ---
import paks_database
import database_config as dbconfig

data_store = {}
database = paks_database.PaksDatabase(dbconfig.Server, dbconfig.Uid, dbconfig.Password, dbconfig.Database)


def is_valid_tckn(tckn):
    return tckn.isdigit() and len(tckn) == 11


# --- YENİ EKLENEN FONKSİYON ---
def is_valid_hex_string(data):
    """
    Gelen verinin geçerli bir Hex string olup olmadığını kontrol eder.
    1. Boş olmamalı.
    2. Uzunluğu çift sayı olmalı (Her 2 karakter 1 byte ifade eder).
    3. Sadece hex karakterler (0-9, a-f, A-F) içermeli.
    """
    if not data:
        return False
    if len(data) % 2 != 0:
        return False
    return all(c in string.hexdigits for c in data)


# ------------------------------

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

            # --- TCKN KONTROLÜ ---
            if not is_valid_tckn(tckn):
                self._set_headers(400)
                self.wfile.write('{"error": "Geçersiz TCKN"}'.encode('utf-8'))
                return

            # --- İSİM KONTROLÜ ---
            if not fullname or len(fullname) > 191:
                self._set_headers(400)
                self.wfile.write('{"error": "Ad Soyad boş olamaz ve 191 karakteri geçemez"}'.encode('utf-8'))
                return

            # --- YENİ EKLENEN: PARMAK İZİ VERİSİ (INFO) KONTROLÜ ---
            if not is_valid_hex_string(info):
                print(f"Hatalı veri formatı denemesi. TCKN: {tckn}")
                self._set_headers(400)
                self.wfile.write(
                    '{"error": "Geçersiz parmak izi verisi. Hex formatında ve çift uzunlukta olmalıdır."}'.encode(
                        'utf-8'))
                return
            # -------------------------------------------------------

            person = database.selectPeopleWithTCKN(tckn)

            if len(person) <= 0:
                if database.insert_person(fullname, tckn):
                    print("Kişi oluşturma başarılı", fullname, tckn)
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"message": "Kayıt eklenirken bir hata oluştu", "tckn": tckn}).encode())
                    return  # Hata durumunda return eklemek iyi olur, aşağı devam etmemeli

            # Kişi ID'sini tekrar çek
            person_ver = database.selectPeopleWithTCKN(tckn)
            if len(person_ver) > 0:
                person_id = person_ver[0][0]

                if database.insert_person_fingerprint(person_id, info):
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"message": "Kayıt eklendi", "tckn": tckn}).encode())
                else:
                    self._set_headers(400)
                    self.wfile.write(
                        json.dumps({"message": "Parmak izi kaydedilirken hata oluştu", "tckn": tckn}).encode())
            else:
                self._set_headers(400)
                self.wfile.write(json.dumps({"message": "Kişi ID alınamadı", "tckn": tckn}).encode())

        except Exception as e:
            self._set_headers(400)
            print(f"Server Error: {e}")
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

            # Not: data_store kullanımı orijinal kodda vardı ama db kullanılıyor gibi.
            # Yine de orijinal mantığı bozmadım, sadece güvenlik ekledim.
            if tckn not in data_store:
                # Burada veritabanı silme işlemi eksik olabilir ama talep bu değildi.
                pass

            if tckn in data_store:
                del data_store[tckn]

            self._set_headers(200)
            self.wfile.write(json.dumps({"message": "Kayıt silindi (Cache)", "tckn": tckn}).encode())

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