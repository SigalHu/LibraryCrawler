import urllib.request
import re


class LibraryCrawler:
	__url = None
	__url_pic = None
	__name_pic = {'封面页': 'cov%03d.jpg',
	              '书名页': 'bok%03d.jpg',
	              '版权页': 'leg%03d.jpg',
	              '前言页': 'fow%03d.jpg',
	              '目录页': '!%05d.jpg',
	              '正文页': '%06d.jpg'}

	def __init__(self, url):
		re.match(re.compile(''), url)
		self.__url = url
		resp = urllib.request.urlopen(url)
		page = resp.read().decode('utf-8')
		url_pic = re.findall(re.compile(r'var str=\'(.*?)\''), page)
		if len(url_pic):
			self.__url_pic = url_pic[0]
		else:
			raise Exception('获取地址失败！')

	def down_pic(self):
		name_pic = 'cov001.jpg'
		for ii in range(1000):
			urllib.request.urlretrieve(url_pic[0] + name_pic, str(ii) + '.jpg')


if __name__ == '__main__':
	save_path = 'files'
	url = 'http://202.119.70.51:8088/Jpath_sky/DsrPath.do?code=98F8696F0AF9722EB74FE00FD059A84B&ssnumber=13803029&netuser=1&jpgreadmulu=1&displaystyle=0&channel=0&ipside=0'
	lc = LibraryCrawler(url)
