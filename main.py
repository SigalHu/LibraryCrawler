import urllib.request
import urllib.parse
import http.cookiejar
import re
import os
import time
from reportlab.pdfgen.canvas import Canvas
from PIL import Image
from tqdm import tqdm
from bs4 import BeautifulSoup


class LibraryCrawler:
	__book_page_url = None
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

	def __init_para(self, book_url):
		resp = urllib.request.urlopen(book_url)
		html_page = resp.read().decode('utf-8')

		results = re.findall(re.compile('<title>(.*?)</title>'), html_page)
		if len(results):
			self.__book_name = re.sub(re.compile(r'[\\/:*?"<>|]+'), ' ', results[0]).strip(' ')
		else:
			raise Exception('获取书籍地址失败！')

		results = re.findall(re.compile(r'var str=\'(.*?)\''), html_page)
		if len(results):
			self.__book_page_url = results[0]
		else:
			raise Exception('获取书籍地址失败！')

		results = re.findall(re.compile(
			r'pages :\[\[(.*?),(.*?)\],\[(.*?),(.*?)\],\[(.*?),(.*?)\],\[(.*?),(.*?)\], \[(.*?),(.*?)\], \[spage, epage\]'),
			html_page)
		if len(results) and len(results[0]) == (len(self.__book_items) - 1) * 2:
			for ii, key in zip(range(len(self.__book_items) - 1), self.__book_items.keys()):
				self.__set_book_items(key, int(results[0][2 * ii]), int(results[0][2 * ii + 1]))
		else:
			raise Exception('获取书籍栏目失败！')

		results = re.findall(re.compile(r'var spage = (.*?), epage = (.*?);'), html_page)
		if len(results) and len(results[0]) == 2:
			self.__set_book_items('正文页', int(results[0][0]), int(results[0][1]))
		else:
			raise Exception('获取书籍栏目失败！')

	def __get_book_url(self, book_info_url):
		ssid_para = {'callback': 'SigalHu',
		             'isbn': '',
		             'bookName': '',
		             'author': '',
		             'eCode': 'utf-8'}
		# 获取书籍信息页面
		resp = urllib.request.urlopen(book_info_url)
		html_page = resp.read().decode('utf-8')

		# 获取请求参数
		soup = BeautifulSoup(html_page, 'html.parser')
		res = soup.find('dt', text=re.compile(r'ISBN及定价'))
		if res is None:
			res = soup.find('dt', text=re.compile(r'标准书号'))
		if res is not None:
			isbn = res.find_next_sibling('dd').string.strip()
			if isbn is not None:
				ssid_para['isbn'] = isbn.split(' ')[0].split("/")[0]

		res = soup.find('dt', text=re.compile(r'题名/责任者'))
		if res is not None:
			book_name = ''
			for child_tag in res.find_next_sibling('dd').children:
				book_name += child_tag.string
			book_name = book_name.strip().split('/')
			ssid_para['bookName'] = book_name[0]
			if len(book_name) > 1:
				ssid_para['author'] = book_name[1]

		res = soup.find('dt', text=re.compile(r'个人责任者'))
		if res is not None:
			author = ''
			for child_tag in res.find_next_sibling('dd').children:
				author += child_tag.string
			author = author.strip().split(' ')
			if len(author) > 0:
				ssid_para['author'] = author[0]

		# 获取ssid
		resp = urllib.request.urlopen(r'http://202.119.70.51:8088/servlet/isExitJson?' + urllib.parse.urlencode(ssid_para))
		ssid_data = re.findall(re.compile(r'"ssid":"(\d+)"'), resp.read().decode('utf-8'))
		if len(ssid_data) == 0:
			raise Exception('该书籍不存在电子版！')

		# 获取book_cookie
		cookies = http.cookiejar.CookieJar()
		handler = urllib.request.HTTPCookieProcessor(cookies)
		opener = urllib.request.build_opener(handler)
		resp = opener.open(r'http://202.119.70.51:8088/catchpage/URL.jsp?BID=' + ssid_data[0])
		book_cookie = ''
		for cookie in cookies:
			book_cookie += '%s=%s;' % (cookie.name, cookie.value)

		# 获取book_url
		resq = urllib.request.Request(r'http://202.119.70.51:8088/markbook/guajie.jsp?BID=' + ssid_data[0],
		                              headers={'Cookie': book_cookie})
		resp = opener.open(resq)
		resq = urllib.request.Request(r'http://202.119.70.51:8088/getbookread?BID=' + ssid_data[
			0] + '&ReadMode=0&jpgread=0&displaystyle=0&NetUser=&page=',
		                              headers={'Cookie': book_cookie})
		resp = opener.open(resq)
		book_url = r'http://202.119.70.51:8088' + urllib.parse.unquote(resp.read().decode('utf-8'))
		return book_url

	def download_jpg(self, book_info_url, save_path):
		book_url = self.__get_book_url(book_info_url)
		self.__init_para(book_url)

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
					urllib.request.urlretrieve(self.__book_page_url + pic_name, os.path.join(path, pic_name))
				time.sleep(0.1)
		print('《%s》下载完毕！' % self.__book_name)

	def download_pdf(self, book_info_url, save_path):
		book_url = self.__get_book_url(book_info_url)
		self.__init_para(book_url)

		if os.path.exists(save_path):
			if not os.path.isdir(save_path):
				raise Exception('保存路径错误！')
		else:
			os.mkdir(save_path)
		pdf_path = os.path.join(save_path, self.__book_name + '.pdf')
		if os.path.exists(pdf_path):
			print('文件：%s 已存在，停止下载《%s》！' % (pdf_path, self.__book_name))
			return
		resp = urllib.request.urlopen(self.__book_page_url + self.__book_items['正文页'][0] % self.__book_items['正文页'][1])
		img = Image.open(resp)
		canvas = Canvas(pdf_path, pagesize=img.size)

		print('开始下载《%s》...' % self.__book_name)
		for key, value in zip(self.__book_items.keys(), self.__book_items.values()):
			if value[1] <= value[2]:
				print('正在下载%s...' % key)
				time.sleep(0.1)
				for ii in tqdm(range(value[1], value[2] + 1)):
					pic_name = value[0] % ii
					canvas.drawImage(self.__book_page_url + pic_name, 0, 0, img.size[0], img.size[1])
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
	url = r'http://202.119.70.22:888/opac/item.php?marc_no=0000739835'
	lc = LibraryCrawler()
	lc.download_pdf(url,save_path)
