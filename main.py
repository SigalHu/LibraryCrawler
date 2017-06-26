import urllib.request
import re
import os

import time
from tqdm import tqdm


class LibraryCrawler:
	__url = None
	__url_pic = None
	__book_name = None
	__bool_items = {'封面页': ['cov%03d.jpg'],
	                '书名页': ['bok%03d.jpg'],
	                '版权页': ['leg%03d.jpg'],
	                '前言页': ['fow%03d.jpg'],
	                '目录页': ['!%05d.jpg'],
	                '正文页': ['%06d.jpg']}

	def __init__(self, url):
		re.match(re.compile(''), url)
		self.__url = url
		resp = urllib.request.urlopen(url)
		page = resp.read().decode('utf-8')

		results = re.findall(re.compile('<title>(.*?)</title>'), page)
		if len(results):
			self.__book_name = re.sub(re.compile(r'[\\/:*?"<>|]+'), ' ', results[0]).strip(' ')
		else:
			raise Exception('获取书籍地址失败！')

		results = re.findall(re.compile(r'var str=\'(.*?)\''), page)
		if len(results):
			self.__url_pic = results[0]
		else:
			raise Exception('获取书籍地址失败！')

		results = re.findall(re.compile(
			r'pages :\[\[(.*?),(.*?)\],\[(.*?),(.*?)\],\[(.*?),(.*?)\],\[(.*?),(.*?)\], \[(.*?),(.*?)\], \[spage, epage\]'),
			page)
		if len(results) and len(results[0]) == (len(self.__bool_items) - 1) * 2:
			for ii, key in zip(range(len(self.__bool_items) - 1), self.__bool_items.keys()):
				self.__bool_items[key].append(int(results[0][2 * ii]))
				self.__bool_items[key].append(int(results[0][2 * ii + 1]))
		else:
			raise Exception('获取书籍栏目失败！')

		results = re.findall(re.compile(r'var spage = (.*?), epage = (.*?);'), page)
		if len(results) and len(results[0]) == 2:
			self.__bool_items['正文页'].append(int(results[0][0]))
			self.__bool_items['正文页'].append(int(results[0][1]))
		else:
			raise Exception('获取书籍栏目失败！')

	def down_pic(self, save_path):
		if os.path.exists(save_path):
			if not os.path.isdir(save_path):
				raise Exception('保存路径错误！')
		else:
			os.mkdir(save_path)
		root_path = os.path.join(save_path, self.__book_name)
		if os.path.exists(root_path):
			print('文件夹：%s 已存在，停止下载《%s》！' % (root_path, self.__book_name))
			return
		os.mkdir(root_path)

		print('开始下载《%s》...' % self.__book_name)
		for key, value in zip(self.__bool_items.keys(), self.__bool_items.values()):
			if value[1] <= value[2]:
				print('正在下载%s...' % key)
				time.sleep(0.1)
				path = os.path.join(root_path, key)
				os.mkdir(path)
				for ii in tqdm(range(value[1], value[2] + 1)):
					pic_name = value[0] % ii
					urllib.request.urlretrieve(self.__url_pic + pic_name, os.path.join(path, pic_name))
				time.sleep(0.1)
		print('《%s》下载完毕！' % self.__book_name)


if __name__ == '__main__':
	save_path = 'files'
	url = 'http://202.119.70.51:8088/Jpath_sky/DsrPath.do?code=851A0AEAEB840FDBC04C37FA4E3DEEF2&ssnumber=13877466&netuser=1&jpgreadmulu=1&displaystyle=0&channel=0&ipside=0'
	lc = LibraryCrawler(url)
	lc.down_pic(save_path)
