from urllib import request, error, response, parse
from bs4 import *
import http.cookiejar
import html,json
import hashlib

def mydecode(data):
    '''将二进制数据转码成字符 ，万一出错 返回None'''
    types = ['utf-8','gb2312','gbk','iso-8859-1']   #可以添加其他字符编码
    for type in types:
        try:
            return data.decode(type)
        except:
            pass
    return None

def openRequest(url, method='GET', data=None):
    global cj, opener, init
    if not init:
        init = True
        cj = http.cookiejar.CookieJar()
    opener = request.build_opener(request.HTTPCookieProcessor(cj))
    req = request.Request(url)
    req.add_header('User-agent', 'Mozilla/28.0')
    request.install_opener(opener)
    if data:
        return request.urlopen(req,data)
    else:
         return request.urlopen(req)

def GET(url):
    '''get请求页面 并返回已经解码的url对应的页面'''
    r = openRequest(url)
    return mydecode(r.read())

def POST(url, data, head=[]):
    '''post数据 并返回已经解码的url对应的页面'''
    r = request.Request(url)
    for k, v in head:
        r.add_header(k, v)
    resp = openRequest(url, 'POST', data)
    return  mydecode(resp.read())

def out(data):
    '''输出调试信息'''
    if debug:
        print('-'*20)
        print(data)

def login(username, password, school):
    '''登录获取session以发送数据，并得到课程的结果页'''
    url = 'http://passport2.chaoxing.com/login'
    data = {
        'pid': -1,
        'pidName': '',
        'fid': str(school),
        'fidName': '',
        'uname': str(username),
        'password': str(password)
    }

    h = [("Content-Type", "application/x-www-form-urlencoded;charset=utf-8")]
    data = parse.urlencode(data).encode('utf-8')
    return POST(url, data, head=h)

def urltoMap(url):
    #url = input('please input:')
    p = parse.urlparse(url).query
    map = {}
    for key_value in p.split('&'):
        k,v = key_value.split('=')
        map[k] = v
    return map

def getChapterList(doc):
    '''获取一门课程对应的所有章节列表'''
    soup = BeautifulSoup(doc)
    l = []
    for h3 in soup.find_all('h3', class_='clearfix'):
        url = h3.a['href']
        name = h3.find('span', class_='articlename').a['title']
        passed = '100%' in h3.a.span.text
        l.append( (url, name, passed))
    return l


def getCourseList(doc):
    '''获取用户选择的课程列表'''
    soup = BeautifulSoup(doc)
    childsrc = soup.find('iframe')['src']       #因为课程在iframe里面 显示的
    doc = GET(childsrc)
    soup = BeautifulSoup(doc)
    courses = []
    for div in soup.find_all('div', class_='Mconright'):
        url = div.h3.a['href']
        url = parse.urljoin(childsrc, url)
        name = div.h3.a.string
        courses.append(url)
    return courses

def passAChapter(url):
    '''跳过一个章节'''
    map = urltoMap(url)
    url = 'http://mooc.chaoxing.com/knowledge/cards'
    data = {
        'clazzid': map['classId'],
        'courseid': map['courseId'],
        'knowledgeid': map['chapterId'],
        'num': 0,
        'v': '20140815',
    }
    url += "?"+parse.urlencode(data)
    doc = GET(url)
    #在页面的js中抽取有用的信息
    soup = BeautifulSoup(doc)
    script = str(soup.find_all('script')[4])
    start = script.find('try{')
    end = script.find('};')
    substr  = script[start+13:end+1]

    d = jsonTodict( substr)
    objid = d['attachments'][0]['objectId']
    t = getDuration(objid)        #知道这个视频共有多少秒

    s1 = '>.MY[Or/s<?OJC]'        #播放器用的 ‘盐’ 用来加密播放进度信息  md5(solt+time*1000)
    s2 = str((t-1)*1000)
    m = hashlib.md5()
    m.update((s1+s2).encode('utf-8'))
    enc = m.hexdigest()

    data = {
        'clazzId':      d['defaults']['clazzId'],
        'jobid':         d['attachments'][0]['jobid'],
        'objectId':     objid,
        'otherInfo':    d['attachments'][0]['otherInfo'],
        'rt':           0.9,
        'dtype':        'Video',
        'enc':           enc,         # md5(solt+time*1000)
        'clipTime':     ('0_%d' %t),          #0_maxsec
        'duration':      t,         #sec
        'playingTime':  t-1,          #secnow
        'isdrag':       3,
    }
    p = parse.urlencode(data)
    url = 'http://ptr.chaoxing.com/multimedia/log?'+p
    doc = GET(url)
    return 'true' in doc            #如果课程已经通过 doc就会返回{'ispassed':true}字符串

def getDuration(objid):
    '''获取objid对应的视频有多少秒 返回int'''
    url = "http://ptr.chaoxing.com/ananas/status/"+str(objid)
    doc = GET(url)
    i1 = doc.find('"duration"')
    i1 = doc.find(':', i1)
    i2 = doc.find(',', i1)
    t = int(doc[i1+1:i2])
    return t

def jsonTodict(jsontext):
    d=json.JSONDecoder().decode(jsontext)
    return d

def main(user, password, school):
    doc = login(user, password, school)
    if "用户登录" in doc:
        print("登录失败,请查看err.html")
        with open('err.html', 'w') as err:
            err.write(doc)
        return
    else:
        print('login success')
    courselist = getCourseList(doc)
    if courselist:
        print('get courselist success')
    allclassurl = []            #保存所有的小节
    for course in courselist:   #遍历每一个课程
        #2015-03-29 23:01:03 添加了过滤非法字符的功能 原因见评论1
        course = course.replace('\n', '').replace('\t', '').replace('\r', '').replace('//', '/').replace(':/', '://')
        doc = GET(course)
        chptlist = getChapterList(doc)
        allclassurl+=chptlist
    else:
        print('get classurl finished')
    for url, name, passed in allclassurl:
        if not passed:      #如果没有完成
            import threading
            threading.Thread(target=worker, args=(name,url)).start()
    print('all finished')

def worker(name, url):
    passed = passAChapter(url)
    print('%s:\t\t%s'%(name, passed))

if __name__=="__main__":
    global debug, init
    debug = True
    init = False

    user = "你的学号"
    password = "你的密码"
    school = "学校id"
    try:
        main(user, password, school)
    except:
        print('出现错误，程序退出')
