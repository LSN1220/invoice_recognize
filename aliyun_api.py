# python3
import urllib.request
import urllib.parse
import json
import time
import base64
with open('./data/00001.png', 'rb') as f:  # 以二进制读取本地图片
    data = f.read()
    encodestr = str(base64.b64encode(data),'utf-8')
#请求头
headers = {
    'Authorization': 'APPCODE d1f79869dbc5449da19a7dff51df1649',
    'Content-Type': 'application/json; charset=UTF-8'
}
def posturl(url,data={}):
    try:
        params=json.dumps(data).encode(encoding='UTF8')
        req = urllib.request.Request(url, params, headers)
        r = urllib.request.urlopen(req)
        html =r.read()
        r.close()
        return html.decode("utf8")
    except urllib.error.HTTPError as e:
        print(e.code)
        print(e.read().decode("utf8"))
    time.sleep(1)
if __name__=="__main__":
    url_request="https://ocrapi-invoice.taobao.com/ocrservice/invoice"
    data = {'img': encodestr}
    start = time.time()
    html = posturl(url_request, data)
    print(html)
    print('time:', time.time() - start)