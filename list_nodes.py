import json,urllib.request,os
os.environ.pop('HTTP_PROXY',None);os.environ.pop('HTTPS_PROXY',None)
d=json.load(urllib.request.urlopen('http://127.0.0.1:8188/object_info'))
print('\n'.join(sorted(k for k in d if 'gguf' in k.lower() or ('unet' in k.lower() and 'loader' in k.lower()))))
