import urllib.request
import re
import os
import time
from reportlab.pdfgen.canvas import Canvas
from PIL import Image
from tqdm import tqdm
from bs4 import BeautifulSoup


class LibraryCrawler:
	__url_pic = None
	__book_name = None
	__book_items = {'封面页': ['cov%03d.jpg'],
	                '书名页': ['bok%03d.jpg'],
	                '版权页': ['leg%03d.jpg'],
	                '前言页': ['fow%03d.jpg'],
	                '目录页': ['!%05d.jpg'],
	                '正文页': ['%06d.jpg']}

	@property
	def book_name(self):
		return self.__book_name

	@property
	def book_items(self):
		res = {}
		for key, value in zip(self.__book_items.keys(), self.__book_items.values()):
			if len(value) == 3:
				res.setdefault(key, value[1:])
			else:
				res.setdefault(key)
		return res

	def __set_book_items(self, key, start_page, end_page):
		if key not in self.__book_items.keys():
			raise Exception('参数初始化失败！')
		length = len(self.__book_items[key])
		if length == 1:
			self.__book_items[key].append(start_page)
			self.__book_items[key].append(end_page)
		elif length == 3:
			self.__book_items[key][1] = start_page
			self.__book_items[key][2] = end_page
		else:
			self.__book_items[key] = [self.__book_items[key][0]]
			self.__book_items[key].append(start_page)
			self.__book_items[key].append(end_page)

	def __init_para(self, url):
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
		if len(results) and len(results[0]) == (len(self.__book_items) - 1) * 2:
			for ii, key in zip(range(len(self.__book_items) - 1), self.__book_items.keys()):
				self.__set_book_items(key, int(results[0][2 * ii]), int(results[0][2 * ii + 1]))
		else:
			raise Exception('获取书籍栏目失败！')

		results = re.findall(re.compile(r'var spage = (.*?), epage = (.*?);'), page)
		if len(results) and len(results[0]) == 2:
			self.__set_book_items('正文页', int(results[0][0]), int(results[0][1]))
		else:
			raise Exception('获取书籍栏目失败！')

	def __get_book_url(self,html_page):
		soup = BeautifulSoup(html_page, 'html.parser')
		results = soup.select('.booklist')
		for res in results:
			book_info = re.findall(re.compile(r'<dt>(.*?):</dt>'),res)
			if len(book_info) == 1:
				book_info = book_info[0]
			else:
				pass


	def download_jpg(self, url, save_path):
		self.__init_para(url)

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
		for key, value in zip(self.__book_items.keys(), self.__book_items.values()):
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

	def download_pdf(self, url, save_path):
		self.__init_para(url)

		if os.path.exists(save_path):
			if not os.path.isdir(save_path):
				raise Exception('保存路径错误！')
		else:
			os.mkdir(save_path)
		pdf_path = os.path.join(save_path, self.__book_name + '.pdf')
		if os.path.exists(pdf_path):
			print('文件：%s 已存在，停止下载《%s》！' % (pdf_path, self.__book_name))
			return
		resp = urllib.request.urlopen(self.__url_pic + self.__book_items['正文页'][0] % self.__book_items['正文页'][1])
		img = Image.open(resp)
		canvas = Canvas(pdf_path, pagesize=img.size)

		print('开始下载《%s》...' % self.__book_name)
		for key, value in zip(self.__book_items.keys(), self.__book_items.values()):
			if value[1] <= value[2]:
				print('正在下载%s...' % key)
				time.sleep(0.1)
				for ii in tqdm(range(value[1], value[2] + 1)):
					pic_name = value[0] % ii
					canvas.drawImage(self.__url_pic + pic_name, 0, 0, img.size[0], img.size[1])
					canvas.showPage()
				time.sleep(0.1)
		canvas.save()
		print('《%s》下载完毕！' % self.__book_name)

	def jpg_to_pdf(self, jpg_root_dir, save_path):
		if not os.path.isdir(jpg_root_dir):
			raise Exception('文件夹：%s 不存在！' % jpg_root_dir)
		self.__book_name = os.path.split(jpg_root_dir)[1]
		pdf_path = os.path.join(save_path, self.__book_name + '.pdf')
		if os.path.exists(pdf_path):
			print('文件：%s 已存在，停止下载《%s》！' % (pdf_path, self.__book_name))
			return

		value_path = os.path.join(jpg_root_dir, '正文页/' + self.__book_items['正文页'][0] % 1)
		if not os.path.isfile(value_path):
			raise Exception('文件夹：%s 无法被识别！' % jpg_root_dir)
		img = Image.open(value_path)
		canvas = Canvas(pdf_path, pagesize=img.size)

		print('开始转换《%s》...' % self.__book_name)
		for key, value in zip(self.__book_items.keys(), self.__book_items.values()):
			key_path = os.path.join(jpg_root_dir, key)
			if os.path.isdir(key_path):
				print('正在转换%s...' % key)
				ii = 1
				while True:
					value_path = os.path.join(key_path, value[0] % ii)
					if not os.path.isfile(value_path):
						self.__set_book_items(key, 1, ii - 1)
						break
					canvas.drawImage(value_path, 0, 0, img.size[0], img.size[1])
					canvas.showPage()
					ii += 1
			else:
				self.__set_book_items(key, 1, 0)
		canvas.save()
		print('《%s》转换完毕！' % self.__book_name)


if __name__ == '__main__':
	save_path = 'files'
	url = 'http://202.119.70.51:8088/Jpath_sky/DsrPath.do?code=B9F43CAD3FD709CD577FA3A6F1D46ECE&ssnumber=13176387&netuser=1&jpgreadmulu=1&displaystyle=0&channel=0&ipside=0'
	lc = LibraryCrawler()
	# lc.download_pdf(url,save_path)
	lc.jpg_to_pdf(r'''files/HTML5与CSS3网页设计入门与提高''', save_path)
	print(lc.book_name)
	print(lc.book_items)
