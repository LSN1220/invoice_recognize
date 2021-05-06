# encoding:utf-8

import requests
import base64
import time
'''
增值税发票识别
'''
# client_id 为官网获取的AK， client_secret 为官网获取的SK
host = 'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=mvS45wexdDMRH656dIfdhoN4&client_secret=ylWi4rCGbAGbFDpSOgDpfnCXSyWxGdsB'
response = requests.get(host)
if response:
    request_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/vat_invoice"
    # 二进制方式打开图片文件
    f = open('./data/00001.png', 'rb')
    img = base64.b64encode(f.read())

    params = {"image":img}
    access_token = response.json()['access_token']
    request_url = request_url + "?access_token=" + access_token
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    start = time.time()
    response = requests.post(request_url, data=params, headers=headers)
    if response:
        print (response.json())
        print('time:', time.time() - start)