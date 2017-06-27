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
	__headers = {'Cookie': ''}

	@property
	def book_name(self):
		return self.__book_name

	@property
	def book_items(self):
		res = {}
		for key, value in zip(self.__book_items.keys(), self.__book_items.values()):
			res[key] = value[1:] if len(value) == 3 else None
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
		resp = urllib.request.urlopen(
			r'http://202.119.70.51:8088/servlet/isExitJson?' + urllib.parse.urlencode(ssid_para))
		ssid_data = re.findall(re.compile(r'"ssid":"(\d+)"'), resp.read().decode('utf-8'))
		if len(ssid_data) == 0:
			raise Exception('《%s》不存在电子版！' % ssid_para['bookName'])

		# 获取book_cookie
		cookies = http.cookiejar.CookieJar()
		handler = urllib.request.HTTPCookieProcessor(cookies)
		opener = urllib.request.build_opener(handler)
		resq = urllib.request.Request(r'http://202.119.70.51:8088/catchpage/URL.jsp?BID=' + ssid_data[0],
		                              headers=self.__headers)
		resp = opener.open(resq)
		for cookie in cookies:
			self.__headers['Cookie'] = '%s=%s;' % (cookie.name, cookie.value)
			break

		# 获取book_url
		resq = urllib.request.Request(r'http://202.119.70.51:8088/markbook/guajie.jsp?BID=' + ssid_data[0],
		                              headers=self.__headers)
		resp = opener.open(resq)
		resq = urllib.request.Request(r'http://202.119.70.51:8088/getbookread?BID=' + ssid_data[
			0] + '&ReadMode=0&jpgread=0&displaystyle=0&NetUser=&page=',
		                              headers=self.__headers)
		resp = opener.open(resq)
		book_url = r'http://202.119.70.51:8088' + urllib.parse.unquote(resp.read().decode('utf-8'))
		return book_url

	def __get_book_list(self, html_page):
		soup = BeautifulSoup(html_page, 'html.parser')
		book_info_list = soup.find_all('li', class_='book_list_info')
		book_list = []
		for book_item in book_info_list:
			book_info = {'题名': None,
			             'url': r'http://202.119.70.22:888/opac/item.php?marc_no=',
			             '个人责任者': None,
			             '出版发行项': None}
			book_item = str(book_item)
			res = re.findall(re.compile(r'<a href="item\.php\?marc_no=(.*?)">\d+\.(.*?)</a>'), book_item)
			if len(res) and len(res[0]) == 2:
				book_info['url'] += res[0][0]
				book_info['题名'] = res[0][1]
				res = re.findall(re.compile(r'</span>\s*(.*?)\s*<br>[\n\t\s]*(.*?)[,\s]*(\d*\.?\d*)\s*<br/>'),
				                 book_item)
				if len(res) and len(res[0]) == 3:
					book_info['个人责任者'] = res[0][0]
					book_info['出版发行项'] = '%s %s' % (res[0][1], res[0][2])
				book_list.append(book_info)
		return book_list

	def search_books(self, key_word):
		search_para = {'strSearchType': 'title',
		               'match_flag': 'forward',
		               'historyCount': '0',
		               'strText': key_word,
		               'doctype': 'ALL',
		               'with_ebook': 'on',
		               'displaypg': '10000',
		               'showmode': 'list',
		               'sort': 'CATA_DATE',
		               'orderby': 'desc',
		               'dept': 'ALL',
		               'page': '1'}
		resp = urllib.request.urlopen(
			r'http://202.119.70.22:888/opac/openlink.php?' + urllib.parse.urlencode(search_para))
		html_page = resp.read().decode('utf-8')
		book_list = self.__get_book_list(html_page)

		page_list = re.findall(re.compile(r'<option value=\'\d+\'>(\d+)</option>'), html_page)
		if len(page_list):
			page_list = page_list[:int(len(page_list) / 2)]

		for page_num in page_list:
			search_para['page'] = page_num
			resp = urllib.request.urlopen(
				r'http://202.119.70.22:888/opac/openlink.php?' + urllib.parse.urlencode(search_para))
			html_page = resp.read().decode('utf-8')
			book_list += self.__get_book_list(html_page)
		return book_list

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
	save_path = os.path.abspath('files')
	print('默认保存路径：%s' % save_path)
	user = input('是否修改(y/[n]):')
	if user == 'y' or user == 'Y':
		save_path = input('请输入保存路径：')
	while not os.path.isdir(save_path):
		print('保存路径：%s 不存在！' % save_path)
		save_path = input('请输入保存路径：')

	user_mod = input('''请选择下载模式：
1.根据书籍页面链接下载书籍
2.根据关键词批量下载所有搜索到的书籍
输入相应数字进行选择：''')

	lc = LibraryCrawler()
	while True:
		if user_mod == '1':
			book_url = input('请输入书籍页面链接：')
			try:
				lc.download_pdf(book_url, save_path)
			except Exception as ex:
				print(ex)
		elif user_mod == '2':
			key_word = input('请输入搜索关键词：')
			book_list = lc.search_books(key_word)
			book_num = len(book_list)
			print('共搜索到%d个结果...' % book_num)
			if book_num > 0:
				key_dir_name = re.sub(re.compile(r'[\\/:*?"<>|]+'), ' ', key_word).strip(' ')
				save_path = os.path.join(save_path, key_dir_name)

			for book_item, ii in zip(book_list, range(book_num)):
				print('\n准备下载第 %d/%d 本书籍...' % (ii + 1, book_num))
				try:
					lc.download_pdf(book_item['url'], save_path)
				except Exception as ex:
					print(ex)
			print('\n所有书籍下载完毕！\n')
		else:
			user_mod = input('输入相应数字进行选择(1/2)：')
