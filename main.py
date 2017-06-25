import urllib.request
import re

if __name__ == '__main__':
	save_path = 'files'
	url = 'http://202.119.70.51:8088/Jpath_sky/DsrPath.do?code=0A1BEAAD590CD86026A1D86C57B6E036&ssnumber=13803029&netuser=1&jpgreadmulu=1&displaystyle=0&channel=0&ipside=0'
	resp = urllib.request.urlopen(url)
	page = resp.read().decode('utf-8')
	url_pic = re.findall(re.compile(r'var str=\'(.*?)\''),page)

	name_pic = 'cov001.jpg'
	for ii in range(1000):
		urllib.request.urlretrieve(url_pic[0]+name_pic,str(ii)+'.jpg')

