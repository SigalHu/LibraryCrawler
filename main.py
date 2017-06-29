import urllib.request
import urllib.parse
import http.cookiejar
import re
import os
import time
import datetime
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
		'''
		返回当前下载书名
		:return: 当前下载书名
		'''
		return self.__book_name

	@property
	def book_items(self):
		'''
		返回当前下载书籍相关信息
		:return: 当前下载书籍相关信息
		'''
		res = {}
		for key, value in zip(self.__book_items.keys(), self.__book_items.values()):
			res[key] = value[1:] if len(value) == 3 else None
		return res

	def __generate_ruid(self, ruidIndex=0):
		'''
		产生一个时间戳
		:param ruidIndex: 时间戳索引
		:return: (时间戳, 下一个时间戳索引)
		'''
		if ruidIndex > 100000:
			ruidIndex %= 100000
		now_time = datetime.datetime.now()
		time_str = 'R%s%03d%05d' % (
			datetime.datetime.strftime(now_time, '%Y%m%e%H%M%S'), int(now_time.microsecond / 1000), ruidIndex)
		ruidIndex += 11
		return time_str, ruidIndex

	def __set_book_items(self, key, start_page, end_page):
		'''
		设置当前下载书籍页数信息
		:param key:当前下载书籍相关页名
		:param start_page:相关页名起始页
		:param end_page:相关页名结束页
		:return:无
		'''
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
		'''
		通过南航图书馆书籍在线阅读页面信息初始化类成员变量
		:param book_url: 南航图书馆书籍在线阅读页面链接
		:return:无
		'''
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

	def __get_book_url(self, html_page):
		'''
		通过南航图书馆书籍信息页面获取在线阅读页面链接
		:param html_page:南航图书馆书籍信息页面
		:return:在线阅读页面链接
		'''
		ssid_para = {'callback': 'SigalHu',
		             'isbn': '',
		             'bookName': '',
		             'author': '',
		             'eCode': 'utf-8'}

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
			self.__book_name = re.sub(re.compile(r'[\\/:*?"<>|]+'), ' ', book_name[0]).strip(' ')
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
		'''
		通过南航图书馆书籍搜索结果页面获取搜索结果列表
		:param html_page: 南航图书馆书籍搜索结果页面
		:return: 搜索结果列表
		'''
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
				book_info['题名'] = re.sub(re.compile(r'[\\/:*?"<>|]+'), ' ', res[0][1]).strip(' ')
				res = re.findall(re.compile(r'</span>\s*(.*?)\s*<br>[\n\t\s]*(.*?)[,\s]*(\d*\.?\d*)\s*<br/>'),
				                 book_item)
				if len(res) and len(res[0]) == 3:
					book_info['个人责任者'] = res[0][0]
					book_info['出版发行项'] = '%s %s' % (res[0][1], res[0][2])
				book_list.append(book_info)
		return book_list

	def __get_resource_list_from_url(self, resource_info_url):
		'''
		通过南航非书资源管理平台电子资源信息页面链接获取电子资源列表
		:param resource_info_url: 南航非书资源管理平台电子资源信息页面链接
		:return: 电子资源列表
		'''
		# 获取资源信息页面
		resource_list = []
		resp = urllib.request.urlopen(resource_info_url)
		results = re.findall(re.compile(r'<td>(.*?)</td>'), resp.read().decode('utf-8'))
		if len(results) == 0 and len(results) % 3:
			return resource_list
		for ii in range(0, len(results), 3):
			url = re.findall(re.compile(r'javascript:SubmitURL\("post","(.*?)"\+escape\("(.*?)"\)\)'),
			                 results[ii + 2])
			if len(url) == 1 and len(url[0]) == 2:
				results[ii] = re.sub(re.compile(r'[\\/:*?"<>|]+'), ' ', results[ii]).strip(' ')
				resource_list.append({'题名': results[ii],
				                      'url': url[0][0] + urllib.parse.quote(url[0][1])})
		return resource_list

	def __get_resource_list_from_page(self, lib_page):
		'''
		通过南航图书馆书籍信息页面获取电子资源列表
		:param lib_page: 南航图书馆书籍信息页面
		:return: 电子资源列表
		'''
		js_para = {'srchtype': 'I',
		           'wd': None,
		           'clienttype': 'L',
		           'ISBN': None}
		js_url = r'http://202.119.70.28/emlib4/system/datasource/opacinterface.aspx?'
		resource_list = []

		# 获取请求参数
		soup = BeautifulSoup(lib_page, 'html.parser')
		res = soup.find('dt', text=re.compile(r'^ISBN'))
		if res is None:
			raise Exception('获取电子资源相关参数失败！')
		isbn = res.find_next_sibling('dd').string.strip()
		if isbn is None:
			raise Exception('获取电子资源相关参数失败！')
		isbn = re.findall(re.compile(r'((\d+-)+\d+)'), isbn)
		if len(isbn) == 0 or len(isbn[0]) < 2:
			raise Exception('获取电子资源相关参数失败！')
		js_para['wd'] = isbn[0][0]
		js_para['ISBN'] = isbn[0][0]

		resp = urllib.request.urlopen(js_url + urllib.parse.urlencode(js_para))
		js_page = resp.read().decode('utf-8')
		results = re.findall(re.compile(r'javascript:SubmitURL\("post","(.*?)"\+escape\("(.*?)"\)\)'), js_page)
		if len(results) and len(results[0]) > 1:
			resource_list.append({'题名': self.__book_name,
			                      'url': results[0][0] + urllib.parse.quote(results[0][1])})
		else:
			results = re.findall(re.compile(
				r'(http://202\.119\.70\.28/emlib4/system/datasource/opendataobjectdetails\.aspx\?doRUID=[0-9A-Za-z]+)\\'),
				js_page)
			if len(results) == 0:
				raise Exception('获取电子资源相关参数失败！')
			resource_list = self.__get_resource_list_from_url(results[0])
		return resource_list

	def __get_resource_list(self, html_page):
		'''
		通过南航非书资源管理平台电子资源搜索结果页面获取电子资源列表
		:param html_page: 南航非书资源管理平台电子资源搜索结果页面
		:return: 电子资源列表
		'''
		resource_list = []
		results = re.findall(re.compile(r'record\.r=\'(.*?)\';|record\.set\(\'(.*?)\',\'(.*?)\'\);'), html_page)
		key_list = ['10100001', '15900001', '10400001', '10500001', '331350001']
		ruid = ''
		while len(results):
			resource_info = {'资源': [],
			                 '个人责任者': None,
			                 '出版发行项': None}
			url_info = {'题名': None,
			            'url': None}

			while ruid == '' and len(results):
				ruid = results.pop(0)[0]

			tmp, key, value = results.pop(0)
			if tmp != '':
				ruid = tmp
				continue
			while key not in key_list and len(results):
				tmp, key, value = results.pop(0)
				if tmp != '':
					break
			if tmp != '':
				ruid = tmp
				continue

			if key == '10100001':
				url_info['题名'] = re.sub(re.compile(r'[\\/:*?"<>|]+'), ' ', value).strip(' ')

				tmp, key, value = results.pop(0)
				if tmp != '':
					ruid = tmp
					continue
				while key not in key_list and len(results):
					tmp, key, value = results.pop(0)
					if tmp != '':
						break
				if tmp != '':
					ruid = tmp
					continue
			if key == '15900001':
				resource_info['个人责任者'] = value

				tmp, key, value = results.pop(0)
				if tmp != '':
					ruid = tmp
					continue
				while key not in key_list and len(results):
					tmp, key, value = results.pop(0)
					if tmp != '':
						break
				if tmp != '':
					ruid = tmp
					continue
			if key == '10400001':
				resource_info['出版发行项'] = value

				tmp, key, value = results.pop(0)
				if tmp != '':
					ruid = tmp
					continue
				while key not in key_list and len(results):
					tmp, key, value = results.pop(0)
					if tmp != '':
						break
				if tmp != '':
					ruid = tmp
					continue
			if key == '10500001':
				resource_info['出版发行项'] = value if resource_info['出版发行项'] is None else (' ' + value)

				tmp, key, value = results.pop(0)
				if tmp != '':
					ruid = tmp
					continue
				while key not in key_list and len(results):
					tmp, key, value = results.pop(0)
					if tmp != '':
						break
				if tmp != '':
					ruid = tmp
					continue
			if key == '331350001':
				value_url = re.findall(re.compile(r'javascript:SubmitURL\("post","(.*?)"\+escape\("(.*?)"\)\)'), value)
				if len(value_url) and len(value_url[0]) > 1:
					url_info['url'] = value_url[0][0] + urllib.parse.quote(value_url[0][1])
					resource_info['资源'].append(url_info)
					resource_list.append(resource_info)
				else:
					value_url = self.__get_resource_list_from_url(
						r'http://202.119.70.28/emlib4/format/release/aspx/book_xxxx.aspx?RUID=' + ruid)
					if len(value_url) > 0:
						resource_info['资源'] += value_url
						resource_list.append(resource_info)
			ruid = ''
		return resource_list

	def search_books(self, key_word):
		'''
		通过关键词搜索并返回书籍搜索结果列表
		:param key_word: 搜索关键词
		:return: 书籍搜索结果列表
		'''
		book_list = []
		try:
			search_para = {'strSearchType': 'title',
			               'match_flag': 'forward',
			               'historyCount': '0',
			               'strText': key_word,
			               'doctype': 'ALL',
			               'with_ebook': 'on',
			               'displaypg': '1000',
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
		except Exception as ex:
			print(ex)
			return book_list

	def download_jpg(self, book_info_url, save_path, is_download_resource=False):
		'''
		下载书籍并保存为jpg图片
		:param book_info_url: 南航图书馆书籍信息页面链接
		:param save_path: 保存文件夹
		:param is_download_resource: 是否下载该书籍的电子资源
		:return: 是否下载成功
		'''
		html_page = ''
		if os.path.exists(save_path):
			if not os.path.isdir(save_path):
				raise Exception('保存路径错误！')
		else:
			os.mkdir(save_path)

		try:
			# 获取书籍信息页面
			resp = urllib.request.urlopen(book_info_url)
			html_page = resp.read().decode('utf-8')

			book_url = self.__get_book_url(html_page)
			self.__init_para(book_url)

			root_path = os.path.join(save_path, self.__book_name)
			if os.path.exists(root_path):
				print('文件夹：%s 已存在，停止下载《%s》！' % (root_path, self.__book_name))
				return True
			os.mkdir(root_path)

			print('开始下载《%s》...' % self.__book_name)
			for key, value in zip(self.__book_items.keys(), self.__book_items.values()):
				if value[1] <= value[2]:
					print('正在下载%s...' % key)
					time.sleep(0.1)
					path = os.path.join(root_path, key)
					os.mkdir(path)
					for ii in tqdm(range(value[1], value[2] + 1), unit='页', unit_scale=True, leave=True, miniters=1):
						pic_name = value[0] % ii
						urllib.request.urlretrieve(self.__book_page_url + pic_name, os.path.join(path, pic_name))
					time.sleep(0.1)
			print('《%s》下载完毕！' % self.__book_name)
			return True
		except Exception as ex:
			print(ex)
			return False
		finally:
			try:
				if is_download_resource:
					resource_list = self.__get_resource_list_from_page(html_page)
					for resource in resource_list:
						self.download_resource_from(resource['url'], save_path, resource['题名'])
			except Exception as ex:
				print(ex)
				return False

	def download_pdf(self, book_info_url, save_path, is_download_resource=False):
		'''
		下载书籍并保存为pdf文档
		:param book_info_url: 南航图书馆书籍信息页面链接
		:param save_path: 保存文件夹
		:param is_download_resource: 是否下载该书籍的电子资源
		:return: 是否下载成功
		'''
		html_page = ''
		if os.path.exists(save_path):
			if not os.path.isdir(save_path):
				raise Exception('保存路径错误！')
		else:
			os.mkdir(save_path)

		try:
			# 获取书籍信息页面
			resp = urllib.request.urlopen(book_info_url)
			html_page = resp.read().decode('utf-8')

			book_url = self.__get_book_url(html_page)
			self.__init_para(book_url)

			pdf_path = os.path.join(save_path, self.__book_name + '.pdf')
			if os.path.exists(pdf_path):
				print('文件：%s 已存在，停止下载《%s》！' % (pdf_path, self.__book_name))
				return True
			resp = urllib.request.urlopen(
				self.__book_page_url + self.__book_items['正文页'][0] % self.__book_items['正文页'][1])
			img = Image.open(resp)
			canvas = Canvas(pdf_path, pagesize=img.size)

			print('开始下载《%s》...' % self.__book_name)
			for key, value in zip(self.__book_items.keys(), self.__book_items.values()):
				if value[1] <= value[2]:
					print('正在下载%s...' % key)
					time.sleep(0.1)
					for ii in tqdm(range(value[1], value[2] + 1), unit='页', leave=True, miniters=1):
						pic_name = value[0] % ii
						canvas.drawImage(self.__book_page_url + pic_name, 0, 0, img.size[0], img.size[1])
						canvas.showPage()
					time.sleep(0.1)
			print('正在生成pdf...')
			canvas.save()
			print('《%s》下载完毕！' % self.__book_name)
			return True
		except Exception as ex:
			print(ex)
			return False
		finally:
			try:
				if is_download_resource:
					resource_list = self.__get_resource_list_from_page(html_page)
					for resource in resource_list:
						self.download_resource_from(resource['url'], save_path, resource['题名'])
			except Exception as ex:
				print(ex)
				return False

	def jpg_to_pdf(self, jpg_root_dir, save_path):
		'''
		将jpg图片书籍转换为pdf文档
		:param jpg_root_dir: jpg图片书籍根目录
		:param save_path: 保存文件夹
		:return: 是否转换成功
		'''
		try:
			if not os.path.isdir(jpg_root_dir):
				raise Exception('文件夹：%s 不存在！' % jpg_root_dir)
			self.__book_name = os.path.split(jpg_root_dir)[1]
			pdf_path = os.path.join(save_path, self.__book_name + '.pdf')
			if os.path.exists(pdf_path):
				print('文件：%s 已存在，停止下载《%s》！' % (pdf_path, self.__book_name))
				return True

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
			return True
		except Exception as ex:
			print(ex)
			return False

	def search_books_and_download_jpg(self, key_word, save_path, is_download_resource=False):
		'''
		根据关键词搜索书籍并保存为jpg图片
		:param key_word: 搜索关键词
		:param save_path: 保存文件夹
		:param is_download_resource: 是否下载该书籍的电子资源
		:return: 是否保存成功
		'''
		try:
			search_para = {'strSearchType': 'title',
			               'match_flag': 'forward',
			               'historyCount': '0',
			               'strText': key_word,
			               'doctype': 'ALL',
			               'with_ebook': 'on',
			               'displaypg': '1000',
			               'showmode': 'list',
			               'sort': 'CATA_DATE',
			               'orderby': 'desc',
			               'dept': 'ALL',
			               'page': '1'}
			resp = urllib.request.urlopen(
				r'http://202.119.70.22:888/opac/openlink.php?' + urllib.parse.urlencode(search_para))
			html_page = resp.read().decode('utf-8')
			book_list = self.__get_book_list(html_page)
			book_num = len(book_list)
			print('共搜索到 %d 个结果（第 1 页）...' % book_num)
			if book_num > 0:
				key_dir_name = re.sub(re.compile(r'[\\/:*?"<>|]+'), ' ', key_word).strip(' ')
				save_path = os.path.join(save_path, key_dir_name)

			for book_item, ii in zip(book_list, range(book_num)):
				print('\n准备下载第 %d/%d 本书籍（第 1 页）...' % (ii + 1, book_num))
				try:
					self.download_jpg(book_item['url'], save_path, is_download_resource)
				except Exception as ex:
					print(ex)
			print('\n第 1 页书籍下载完毕！\n')

			page_list = re.findall(re.compile(r'<option value=\'\d+\'>(\d+)</option>'), html_page)
			if len(page_list):
				page_list = page_list[:int(len(page_list) / 2)]

			for page_num in page_list:
				search_para['page'] = page_num
				resp = urllib.request.urlopen(
					r'http://202.119.70.22:888/opac/openlink.php?' + urllib.parse.urlencode(search_para))
				html_page = resp.read().decode('utf-8')
				book_list = self.__get_book_list(html_page)
				book_num = len(book_list)
				print('共搜索到 %d 个结果（第 %s 页）...' % (book_num, page_num))

				for book_item, ii in zip(book_list, range(book_num)):
					print('\n准备下载第 %d/%d 本书籍（第 %s 页）...' % (ii + 1, book_num, page_num))
					try:
						self.download_jpg(book_item['url'], save_path, is_download_resource)
					except Exception as ex:
						print(ex)
				print('\n第 %s 页书籍下载完毕！\n' % page_num)
			return True
		except Exception as ex:
			print(ex)
			return False

	def search_books_and_download_pdf(self, key_word, save_path, is_download_resource=False):
		'''
		根据关键词搜索书籍并保存为pdf文档
		:param key_word: 搜索关键词
		:param save_path: 保存文件夹
		:param is_download_resource: 是否下载该书籍的电子资源
		:return: 是否保存成功
		'''
		try:
			search_para = {'strSearchType': 'title',
			               'match_flag': 'forward',
			               'historyCount': '0',
			               'strText': key_word,
			               'doctype': 'ALL',
			               'with_ebook': 'on',
			               'displaypg': '1000',
			               'showmode': 'list',
			               'sort': 'CATA_DATE',
			               'orderby': 'desc',
			               'dept': 'ALL',
			               'page': '1'}
			resp = urllib.request.urlopen(
				r'http://202.119.70.22:888/opac/openlink.php?' + urllib.parse.urlencode(search_para))
			html_page = resp.read().decode('utf-8')
			book_list = self.__get_book_list(html_page)
			book_num = len(book_list)
			print('共搜索到 %d 个结果（第 1 页）...' % book_num)
			if book_num > 0:
				key_dir_name = re.sub(re.compile(r'[\\/:*?"<>|]+'), ' ', key_word).strip(' ')
				save_path = os.path.join(save_path, key_dir_name)

			for book_item, ii in zip(book_list, range(book_num)):
				print('\n准备下载第 %d/%d 本书籍（第 1 页）...' % (ii + 1, book_num))
				try:
					self.download_pdf(book_item['url'], save_path, is_download_resource)
				except Exception as ex:
					print(ex)
			print('\n第 1 页书籍下载完毕！\n')

			page_list = re.findall(re.compile(r'<option value=\'\d+\'>(\d+)</option>'), html_page)
			if len(page_list):
				page_list = page_list[:int(len(page_list) / 2)]

			for page_num in page_list:
				search_para['page'] = page_num
				resp = urllib.request.urlopen(
					r'http://202.119.70.22:888/opac/openlink.php?' + urllib.parse.urlencode(search_para))
				html_page = resp.read().decode('utf-8')
				book_list = self.__get_book_list(html_page)
				book_num = len(book_list)
				print('共搜索到 %d 个结果（第 %s 页）...' % (book_num, page_num))

				for book_item, ii in zip(book_list, range(book_num)):
					print('\n准备下载第 %d/%d 本书籍（第 %s 页）...' % (ii + 1, book_num, page_num))
					try:
						self.download_pdf(book_item['url'], save_path, is_download_resource)
					except Exception as ex:
						print(ex)
				print('\n第 %s 页书籍下载完毕！\n' % page_num)
			return True
		except Exception as ex:
			print(ex)
			return False

	def search_resources(self, key_word):
		'''
		通过关键词搜索并返回电子资源搜索结果列表
		:param key_word: 搜索关键词
		:return: 电子资源搜索结果列表
		'''
		resource_list = []
		try:
			search_offset = 0
			search_num = 1000
			ruidIndex = 2
			js_url = r'http://202.119.70.28/emlib4/system/datasource/dataobjectabs2.aspx?'
			js_headers = {'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'}
			js_data = {'VIEWRUID': '121bdfa10000f3c351',
			           'F0': 'OR|TITLE|like|' + key_word}
			js_para = {'sc': self.__generate_ruid()[0],
			           'desktopID': 'uncreated',
			           '_debug_': '',
			           'LR': 'allcd',
			           'FR': str(search_offset),  # 搜索结果偏移量
			           'MR': str(search_num),  # 返回搜索结果数
			           'SF': 'title',  # 按照标题排序
			           'ST': 'A',  # 升序排列
			           'RR': None}
			js_para['RR'], ruidIndex = self.__generate_ruid(ruidIndex)

			resq = urllib.request.Request(js_url + urllib.parse.urlencode(js_para), headers=js_headers)
			resp = urllib.request.urlopen(resq, data=urllib.parse.urlencode(js_data).encode('utf-8'))
			js_page = resp.read().decode('utf-8')
			search_offset += search_num

			total_num = re.findall(re.compile(r'p\.SendResultToPortal\(_r,op,(\d*),\d*\);'), js_page)
			if len(total_num) == 0:
				raise Exception('获取电子资源相关参数失败！')
			total_num = int(total_num[0])
			if total_num == 0:
				return []

			resource_list = self.__get_resource_list(js_page)
			while search_offset < total_num:
				js_para['FR'] = str(search_offset)
				js_para['RR'], ruidIndex = self.__generate_ruid(ruidIndex)
				resq = urllib.request.Request(js_url + urllib.parse.urlencode(js_para), headers=js_headers)
				resp = urllib.request.urlopen(resq, data=urllib.parse.urlencode(js_data).encode('utf-8'))
				js_page = resp.read().decode('utf-8')
				search_offset += search_num
				resource_list += self.__get_resource_list(js_page)
			return resource_list
		except Exception as ex:
			print(ex)
			return resource_list

	def download_resource_from(self, resource_url, save_path, resource_name):
		'''
		根据电子资源下载链接下载资源到指定路径
		:param resource_url: 电子资源下载链接
		:param save_path: 保存文件夹
		:param resource_name: 电子资源名（不包含后缀）
		:return: 是否下载成功
		'''
		if os.path.exists(save_path):
			if not os.path.isdir(save_path):
				raise Exception('保存路径错误！')
		else:
			os.mkdir(save_path)

		try:
			resource_name = re.sub(re.compile(r'[\\/:*?"<>|]+'), ' ', resource_name).strip(' ')
			suffix = re.findall(re.compile(r'(\.[^.]*?$)'), resource_url)
			if len(suffix):
				resource_name += suffix[0]
			resource_path = os.path.join(save_path, resource_name)
			if os.path.exists(resource_path):
				raise Exception('%s 已存在！' % resource_name)
			print('开始下载 %s...' % resource_name)
			time.sleep(0.1)

			with tqdm(unit='B', unit_scale=True, leave=True, miniters=1) as t:
				def report_progress(download_num=1, download_size=1, total_size=None):
					if total_size is not None:
						t.total = total_size
					t.update(download_size)

				urllib.request.urlretrieve(resource_url, filename=resource_path,
				                           reporthook=report_progress, data=None)
			time.sleep(0.1)
			print('%s 下载完毕！' % resource_name)
			return True
		except Exception as ex:
			print(ex)
			return False

	def download_resource(self, resource_info_url, save_path):
		'''
		根据南航非书资源管理平台电子资源信息页面链接下载资源到指定路径
		:param resource_info_url: 南航非书资源管理平台电子资源信息页面链接
		:param save_path: 保存文件夹
		:return: 是否下载成功
		'''
		if os.path.exists(save_path):
			if not os.path.isdir(save_path):
				raise Exception('保存路径错误！')
		else:
			os.mkdir(save_path)

		try:
			resource_list = self.__get_resource_list_from_url(resource_info_url)
			if len(resource_list) == 0:
				return True
			for resource in resource_list:
				self.download_resource_from(resource['url'], save_path, resource['题名'])
			return True
		except Exception as ex:
			print(ex)
			return False

	def search_and_download_resources(self, key_word, save_path):
		'''
		根据关键词搜索电子资源并下载到指定路径
		:param key_word: 搜索关键词
		:param save_path: 保存文件夹
		:return: 是否下载成功
		'''
		try:
			search_offset = 0
			search_num = 1000
			ruidIndex = 2
			js_url = r'http://202.119.70.28/emlib4/system/datasource/dataobjectabs2.aspx?'
			js_headers = {'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'}
			js_data = {'VIEWRUID': '121bdfa10000f3c351',
			           'F0': 'OR|TITLE|like|' + key_word}
			js_para = {'sc': self.__generate_ruid()[0],
			           'desktopID': 'uncreated',
			           '_debug_': '',
			           'LR': 'allcd',
			           'FR': str(search_offset),  # 搜索结果偏移量
			           'MR': str(search_num),  # 返回搜索结果数
			           'SF': 'title',  # 按照标题排序
			           'ST': 'A',  # 升序排列
			           'RR': None}
			js_para['RR'], ruidIndex = self.__generate_ruid(ruidIndex)

			resq = urllib.request.Request(js_url + urllib.parse.urlencode(js_para), headers=js_headers)
			resp = urllib.request.urlopen(resq, data=urllib.parse.urlencode(js_data).encode('utf-8'))
			js_page = resp.read().decode('utf-8')
			search_offset += search_num

			total_num = re.findall(re.compile(r'p\.SendResultToPortal\(_r,op,(\d*),\d*\);'), js_page)
			if len(total_num) == 0:
				raise Exception('获取电子资源相关参数失败！')
			total_num = int(total_num[0])

			resource_list = self.__get_resource_list(js_page)
			resource_num = len(resource_list)
			print('共搜索到 %d 个结果（第 1 页）...' % resource_num)
			if resource_num > 0:
				key_dir_name = re.sub(re.compile(r'[\\/:*?"<>|]+'), ' ', key_word).strip(' ')
				save_path = os.path.join(save_path, key_dir_name)

			for resource_item, ii in zip(resource_list, range(resource_num)):
				print('\n准备下载第 %d/%d 个电子资源（第 1 页）...' % (ii + 1, resource_num))
				for resource in resource_item['资源']:
					try:
						self.download_resource_from(resource['url'], save_path, resource['题名'])
					except Exception as ex:
						print(ex)
			print('\n第 1 页书籍下载完毕！\n')

			while search_offset < total_num:
				js_para['FR'] = str(search_offset)
				js_para['RR'], ruidIndex = self.__generate_ruid(ruidIndex)
				resq = urllib.request.Request(js_url + urllib.parse.urlencode(js_para), headers=js_headers)
				resp = urllib.request.urlopen(resq, data=urllib.parse.urlencode(js_data).encode('utf-8'))
				js_page = resp.read().decode('utf-8')
				search_offset += search_num
				page_num = int(search_offset / search_num)

				resource_list = self.__get_resource_list(js_page)
				resource_num = len(resource_list)
				print('共搜索到 %d 个结果（第 %d 页）...' % (resource_num, page_num))

				for resource_item, ii in zip(resource_list, range(resource_num)):
					print('\n准备下载第 %d/%d 个电子资源（第 %d 页）...' % (ii + 1, resource_num, page_num))
					for resource in resource_item['资源']:
						try:
							self.download_resource_from(resource['url'], save_path, resource['题名'])
						except Exception as ex:
							print(ex)
				print('\n第 %d 页书籍下载完毕！\n' % page_num)
			return True
		except Exception as ex:
			print(ex)
			return False


def __main():
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
2.根据书籍页面链接下载书籍以及电子资源
3.根据关键词批量下载所有搜索到的书籍
4.根据关键词批量下载所有搜索到的书籍以及电子资源
5.根据电子资源页面链接下载电子资源
6.根据关键词批量下载所有搜索到的电子资源
输入相应数字进行选择：''')

	lc = LibraryCrawler()
	while True:
		try:
			if user_mod == '1' or user_mod == '2':
				book_url = input('\n请输入书籍页面链接：')
				lc.download_pdf(book_url, save_path, True if user_mod == '2' else False)
			elif user_mod == '3' or user_mod == '4':
				key_word = input('\n请输入搜索关键词：')
				lc.search_books_and_download_pdf(key_word,save_path,True if user_mod == '4' else False)
			elif user_mod == '5':
				resource_url = input('\n请输入电子资源页面链接：')
				lc.download_resource(resource_url, save_path)
			elif user_mod == '6':
				key_word = input('\n请输入搜索关键词：')
				lc.search_and_download_resources(key_word,save_path)
			else:
				user_mod = input('\n输入相应数字进行选择(1--6)：')
		except Exception as ex:
			print(ex)

if __name__ == '__main__':
	__main()
