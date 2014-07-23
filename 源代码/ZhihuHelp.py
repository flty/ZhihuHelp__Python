﻿# -*- coding: utf-8 -*-
import  urllib2
import  re
import  zlib
import  threading
import  time
import  datetime
import  HTMLParser#HTML解码&lt;
import  json#在returnPostHeader中解析Post返回值
import  os#打开更新页面

import  urllib#编码请求字串，用于处理验证码


import  sys#修改默认编码
reload( sys )
sys.setdefaultencoding('utf-8')







import  sqlite3#数据库！

###########################################################
#数据库部分
import  pickle
import  socket#捕获Timeout错误
##################Epub########################################
from    ZhihuEpub   import  *
###########################################################
#所有可复用的函数均已转移至Epub文件内
######################网页内容分析############################
#个人答案页面、收藏夹页面答案连接提取
#由returnAnswerList返回提取的答案链接列表，格式：['/question/21354/answer/15488',]
#网页答案抓取
def SetPicDownload():
    u"""
        *   功能
            *   引导用户进行图片下载设置，返回图片设置代码
                *   0   不下载图片
                *   1   下载普通图片
                *   2   下载高清图
                *   默认为1
        *   输入
            *   无
        *   返回
            *   PicDownload
     """
    try:
        print   u"请选择图片模式，根据提示输入相应数字，回车确认：\n0   ：  不下载任何图片#所生成的电子书最小\n1   ：  只下载标清图片#所生成电子书体积中等,为系统默认值，但对于1000条以上的答案集锦来说体积可能会大到无法接受\n2   ：  下载高清大图#所生成电子书的体积是标清图的4倍，答案量在100条以下时可以考虑使用\n"
        PicDownload =   int(raw_input())
    except  ValueError as e  :
        print   e
        print   u'貌似输入的不是数...自动使用默认值标清模式，点击回车继续运行'
        PicDownload =   1
        raw_input()
    return  PicDownload



def FetchMaxAnswerPageNum(Content=""):#简单搜索比正则更快#OKTag
    u"""
    *   功能
        *   返回答案列表中的最大页码
        *   辅助函数
        *   不抛错
    *   输入
        *   答案列表首页内容
            *   已替换掉所有换行符
    *   返回
        *   答案页码
    """
    try:
        Pos         =   Content.index(u'">下一页</a></span>')
        RightPos    =   Content.rfind(u"</a>",0,Pos)
        LeftPos     =   Content.rfind(u">",0,RightPos)
        MaxPage     =   int(Content[LeftPos+1:RightPos])
        print   u"答案列表共计{}页".format(MaxPage)
        return MaxPage
    except:
        print   u"答案列表共计1页"
        return 1
#答案信息读取
def ThreadWorker(cursor=None,MaxThread=200,RequestDict={},Flag=1):#newCommitTag
    u"""
    *   功能
        *   将待打开的网页分配给每一个线程池迸发执行
        *   将解析所得的答案内容储存于数据库中
        *   主要函数
    *   输入
        *   数据库游标，用于储存答案内容
        *   最大线程数
        *   待打开网页Request字典
        *   标志符
            *   用于对不同类型的内容进行处理
            *   标志符来自CheckUpdate返回值
            *   话题的标志符为4
    *   返回
        *   无
    """
    MaxPage =   len(RequestDict)
    ReDict  =   returnReDict()
    AnswerDictList=[]#储存Dict，一并执行SQL
    html_parser=HTMLParser.HTMLParser()
    ThreadList=[]
    Times       =   0
    ErrorCount  =   0
    LoopFlag    =   True

    for Page in  range(MaxPage):
        ThreadList.append(threading.Thread(target=WorkForFetchUrl,args=(ReDict,html_parser,RequestDict,Page,AnswerDictList,Flag)))
    
    while   Times<10    and LoopFlag:
        print   u'开始第{}遍抓取，本轮共有{}张页面待抓取,共尝试10遍'.format(Times+1,len(ThreadList))
        for Page in  range(MaxPage):
            if  threading.activeCount()-1 <   MaxThread:#实际上是总线程数
                ThreadList[Page].start()#有种走钢丝的感觉。。。
            else    :
                PrintInOneLine(u'正在读取答案页面，线程库中还有{}条线程等待运行'.format(MaxPage-Page))
                time.sleep(1)
        ThreadLiveDetect(ThreadList)

        LoopFlag    =   False
        MaxPage     =   0
        ThreadList  =   []
        for t   in  RequestDict:
            if  RequestDict[t][1]==False:
                ThreadList.append(threading.Thread(target=WorkForFetchUrl,args=(ReDict,html_parser,RequestDict,t,AnswerDictList,Flag)))
                MaxPage     +=  1
                LoopFlag    =   True
        Times   +=  1
        if  LoopFlag:
            print   u'第{}遍答案抓取执行完毕，{}张页面抓取失败,3秒后进行下一遍抓取'.format(Times+1,ErrorCount)
            time.sleep(3)
    DictNo      =   0#美化输出
    DictCountNo =   len(AnswerDictList)
    for Dict    in  AnswerDictList:
        DictNo  +=  1
        PrintInOneLine(u'正在将第{}/{}个答案存入数据库中'.format(DictNo,DictCountNo))
        AppendDictIntoDataBase(cursor,Dict)
    return
def SaveCollectionIndexIntoDB(RequestDict={},CollectionID=0,cursor=None):#PassTag
    u"""
    *   功能：
        *   将收藏夹/话题内容索引储存于数据库中，但_不进行提交_
        *   对于传入的数据，无则新建，有便更新
        *   键为收藏夹/话题ID，值为答案链接
    *   输入
        *   网页请求字典（可以从中提取出答案链接）
        *   目标CollectionID，注：用户名、话题ID、收藏夹ID均可视为不同的CollectionID
        *   数据库游标
    *   返回
        *   无
    """
    AnswerList  =   []
    for t   in  RequestDict:
        try:
            RequestDict[t][0].get_full_url()
        except  AttributeError:
            for i   in   RequestDict[t][0]:
                AnswerList.append(i)
    for i   in  AnswerList:
        rowcount    =   cursor.execute('select  count(CollectionID) from    CollectionIndex where CollectionID=?    and Questionhref=?',(CollectionID,i)).fetchone()[0]
        if  rowcount    ==  0:
            cursor.execute('insert  into CollectionIndex   (CollectionID,Questionhref)  values  (?,?) ',(CollectionID,i))
    return
def AppendDictIntoDataBase(cursor=None,Dict={}) :   #假定已有数据库#PassTag
    u"""
        *   功能
            *   将答案内容及其信息储存于数据库的_AnswerContentTable_与_AnswerInfoTable_表中，但_不进行提交_
            *   对于传入的数据，无则新建，有便更新
            *   键为答案链接，值为答案内容
        *   输入
            *   Dict，待储存字典
            *   数据库游标
        *   返回
            *   无
    """
    #bufDict             =   Dict#python中一切皆引用，如想按值传递必须使用copy.deepcopy
    bufDict                     =   {}
    bufDict['AnswerContent']    =   Dict['AnswerContent']
    bufDict['Questionhref']     =   Dict['Questionhref']
    SaveToDB(cursor=cursor,NeedToSaveDict=bufDict,primarykey='Questionhref',TableName='AnswerContentTable'  )
    del Dict['AnswerContent']
    SaveToDB(cursor=cursor,NeedToSaveDict=Dict   ,primarykey='Questionhref',TableName='AnswerInfoTable'     )
    return 
def CheckUpdate():#检查更新，强制更新#newCommitTag
    u"""
        *   功能
            *   检测更新。
            *   若在服务器端检测到新版本，自动打开浏览器进入新版下载页面
            *   网页请求超时或者版本号正确都将自动跳过
        *   输入
            *   无
        *   返回
            *   无
    """
    print   u"检查更新。。。"
    try:
        UpdateTime  =   urllib2.urlopen(u"http://zhihuhelpbyyzy-zhihu.stor.sinaapp.com/ZhihuHelpUpdateTime.txt",timeout=10)
    except:
        return
    Time        =   UpdateTime.readline().replace(u'\n','').replace(u'\r','')
    url         =   UpdateTime.readline().replace(u'\n','').replace(u'\r','')
    UpdateComment=  UpdateTime.read()#可行？
    if  Time=="2014-07-07":
        return
    else:
        print   u"发现新版本，\n更新说明:{}\n更新日期:{} ，点按回车进入更新页面".format(UpdateComment,Time)
        raw_input(u'新版本下载地址:'+url)
        import  webbrowser
        webbrowser.open_new_tab(url)
    return

def returnReDict():#返回编译好的正则字典#Pass
    u"""
        *   功能
            *   返回编译完成的正则表达式字典
        *   输入
            *   无
        *   返回
             *   无
     """
    Dict    =   {}
    Dict['_Collection_QusetionTitle']   =   re.compile(r'(?<=href="/question/\d{8}">).*?(?=</a></h2>)')
    Dict['_QusetionTitle']              =   re.compile(r'(?<=href="/question/\d{8}/answer/\d{8}">).*?(?=</a></h2>)')
    Dict['_AnswerContent']              =   re.compile(r'(?<=<textarea class="content hidden">).*?(?=<span class="answer-date-link-wrap"><a class="answer-date-link .*?meta-item".*?target="_blank" href="/question/\d{8}/answer/\d{8}">[^<]*</a></span></textarea>)')
    Dict['_AgreeCount']                 =   re.compile(r'(?<=data-votecount=")\d*(?=">)')
    Dict['_QuestionID']                 =   re.compile(r'(?<=target="_blank" href="/question/)\d{8}(?=/answer/\d{8})')#数字位数可能有误#不过对11年的数据也有效，貌似多虑了——除非知乎问题能突破5千万条，否则没必要更新
    Dict['_AnswerID']                   =   re.compile(r'(?<=target="_blank" href="/question/\d{8}/answer/)\d{8}(?=">)')
    Dict['_Questionhref']               =   re.compile(r'(?<=target="_blank" href=")[/question\danswer]{34}(?=">)')
    Dict['_AnswerInfo']                 =   re.compile(r'(<a class="answer-date-link.*?target="_blank" href="/question/\d{8}/answer/\d{8}">.{4}.*?</a></span>)')
    Dict['_UpdateTime']        =   re.compile(r'(?<=target="_blank" href="/question/\d{8}/answer/\d{8}">).{4}.*?(?=</a></span>)')#新版编辑日期提取方式,需要进行二次匹配
    #Dict['_UpdateTime']                =   re.compile(r'(?<=<a class="answer-date-link meta-item" target="_blank" href="/question/\d{8}/answer/\d{8}">).*(?=</a></span>)')#旧版编辑日期提取方式
    #分为13：25、昨天 00:26、2013-05-07三种情况或{『编辑于 00:20  』『编辑于 2014-05-11』『发布于 昨天 19:52』、『发布于 2014-05-24』}，muqianzhengzaijinxing A/B测试，待定,需进一步处理
    Dict['_CommitCount']                =   re.compile(r'(?<=<i class="z-icon-comment"></i>).*?(?= )')#若转化为int失败则是添加评论#即为0条
    Dict['_ID']                         =   re.compile(r'(?<=<a data-tip="p\$t\$)[^"]*(?=" href="/people/)')
    Dict['_UnSuccessName']              =   re.compile(r'(?<=<h3 class="zm-item-answer-author-wrap">).*(?=</h3></div>)')
    Dict['_Sign']                       =   re.compile(r'(?<=<strong title=").*(?=" class="zu-question-my-bio">)')
    Dict['_NoRecord']                   =   re.compile(r'<span class="copyright zu-autohide"><span class="zg-bull">&bull;</span> 禁止转载</span>')#怎么用？   
    Dict['_UserIDLogoAdress']           =   re.compile(r'(?<=src=")http://p\d\.zhimg\.com[/\w]{7}[_\w]{11}\.jpg(?="class="zm-list-avatar)')
    return  Dict
        
def ReadAnswer(ReDict,html_parser,LastDict,text="",Flag=1):#UnitTest#newCommitTag
    u"""
        *   功能
            *   根据待处理目标Flag的不同，分析处理答案，返回处理完之后的答案字典
            *   通过编写正则表达式，对传入的文本不断匹配，以获得所欲求得的信息
        *   输入
            *   ReDict
                *   正则模版
            *   html_parser
                *   网页分析类，用于将实体字符转换为正常字符
            *   LastDict
                *   上一个答案字典
                *   当问题链接缺失时，使用之前的问题链接
            *   text
                *   待处理文本
            *   Flag
                *   模式标志符
        *   返回
             *   处理完成后的标准答案字典
     """

    Dict={}    
    Dict["ID"]              =   ""   ##    
    Dict["Sign"]            =   ""#
    Dict["AgreeCount"]      =   0#
    Dict["CommitCount"]     =   0#
    Dict["QuestionID"]      =   ""#
    Dict["AnswerID"]        =   ""#
    Dict["UpdateTime"]      =   "1970-01-01"#
    Dict["QuestionTitle"]   =   ""  ##
    Dict["Questionhref"]    =   ""#
    Dict["AnswerContent"]   =   ""  ##
    Dict["UserName"]        =   "ErrorName" ##
    Dict['UserIDLogoAdress']=   ''#
    if  text=='':
        return  Dict
    try :#检测禁止转载
        ReDict['_NoRecord'].search(text).group(0)
        return Dict
    except  :
        pass

    def Help_ReadAnswer(t="",flag=True):
        u"""
        #辅助系函数
        *   用于提取答案内容，提高代码复用度    
        *   因为某些项匹配失败后应直接调用默认值，所以添加了Flag以做区分
        """
        try:
            Dict[t]      =   ReDict['_'+t].search(text).group(0)
        except  AttributeError:
            if  flag:
                print   u"没有收集到"   +   t
                print   u"知乎页面结构已变动，程序无法正常运行，快上知乎@姚泽源喊他更新脚本" 
                return  False
            else    :
                pass
        return True

    #特殊处理
    try:
        Dict["AnswerContent"]   =   html_parser.unescape(ReDict['_AnswerContent'].search(text).group(0)).encode("utf-8")
    except  AttributeError:
        print   u"答案内容没有收集到"
        print   u"知乎页面结构已变动，程序无法正常运行，快上知乎@姚泽源喊他更新脚本" 
        return  Dict
    
    if  Flag==1:
        try :
            Dict["QuestionTitle"]   =   ReDict['_QusetionTitle'].search(text).group(0)
        except  AttributeError:
            Dict["QuestionTitle"]   =   LastDict["QuestionTitle"]
    else    :
        try :                                                                             
            Dict["QuestionTitle"]   =   ReDict['_Collection_QusetionTitle'].search(text).group(0)
        except  AttributeError:
            Dict["QuestionTitle"]   =   LastDict["QuestionTitle"]
    try :                               
        ID                  =   ReDict['_ID'].search(text).group(0)
        _UserName    	    =	re.compile(r'(?<=<a data-tip="p\$t\$'+ID+r'" href="/people/'+ID+r'">).*?(?=</a>)')#   这里必须要用到已经捕获的ID，否则没法获得用户名
        Dict["UserName"]    =   _UserName.search(text).group(0)
    except  AttributeError  :
        try :#对应于知乎用户与匿名用户两种情况
            Dict["UserName"]    =   ReDict['_UnSuccessName'].search(text).group(0)
            ID                  =   '404NotFound!'
        except  AttributeError:
            Dict["UserName"]    =   u"知乎用户"
            ID                  =   'ZhihuUser!'

    Dict["ID"]              =   ID
    
    #常规匹配   
    #时间放到最后，因为要靠时间验证是否匹配成功
    #知乎页面结构正在改变，待稳定下来以后再进行修改
    #完成注释添加工作后回来添加对单个问题与答案的处理
    for t   in  ["AgreeCount","AnswerInfo"]:
        if  Help_ReadAnswer(t):
            pass
        else:
            return Dict
    for t   in  ["Questionhref","QuestionID","AnswerID","UpdateTime"]:
        try:
            Dict[t]      =   ReDict['_'+t].search(Dict['AnswerInfo']).group(0)  
        except  AttributeError:
            print   t+u"没有收集到"   
            ErrorReturn(u"知乎页面结构已变动，程序无法正常运行，快上知乎@姚泽源喊他更新脚本" )
    for t   in  ['UserIDLogoAdress','Sign','CommitCount']:    
        if  Help_ReadAnswer(t,False):
            pass
        else:
            return Dict
    try:
        Dict["CommitCount"]     =   int(Dict["CommitCount"])
    except  :#类型转换失败即为没有评论
        Dict["CommitCount"]     =   0
    Dict["Questionhref"]        =   'http://www.zhihu.com'+Dict["Questionhref"]
    
    if  len(Dict["UpdateTime"])!=10 :        
        if  len(Dict["UpdateTime"])!=5  :
            Dict["UpdateTime"]  =   time.strftime(u'%Y-%m-%d',time.localtime(time.time()-86400))#昨天
        else    :
            Dict["UpdateTime"]  =   time.strftime(u'%Y-%m-%d',time.localtime(time.time()))#今天
    del Dict['AnswerInfo']
    return Dict

def WorkForFetchUrl(ReDict={},html_parser=None,RequestDict={},Page=0,AnswerDictList=[],Flag=1):#抓取回答链接#注意，Page是字符串#Pass
    u"""
        *   功能
            *   抓取指定答案列表页面进行读取，分析处理得到答案Dict后添加至AnswerDictList中
            *   主要函数
        *   输入
            *   ReDict
                *   正则Map，直接传递给ReadAnswer
            *   html_parser
                *   html解析器，也是直接传递给ReadAnswer
            *   RequestDict
                *   待打开网页Map
            *   Page
                *   待打开页面，使用RequestDict[Page]获取页面Request头
            *   AnswerDictList
                *   答案列表，用于储存提取出的答案字典
            *   Flag
                *   标志符，针对不同的网页类型分别进行处理
        *   返回
             *   无
    """
    print   u"正在抓取第{}页上的答案".format(Page+1)
    AnswerList  =   []
    try :
        k   =   OpenUrl(RequestDict[Page][0]).decode(encoding='utf-8',errors='ignore')#文本内容必须要经过统一编码，否则字符串操作会出现各种未定义行为
    except  ValueError as  e:#对于40X错误不再继续读取
        print   e
        ErrorReportText(Info=u'读取答案内容出错\t:\t'+str(e))  
        RequestDict[Page][1]=True
        return
    except  IOError as e    :#解压缩错误
        print   e
        return
    if  k=='':#网页未成功打开
        return
    if  Flag==4:
        k       =   k.split('<div class="content"')#话题与普通的页面结构不一样
    else:
        k       =   k.split('<div class="zm-item"')
    Dict    =   {}
    for t   in  range(1,len(k)):# 为0则何如
        if  t==(len(k)-1):
            k[t]    =   k[t].split('<div class="zm-invite-pager">')[0]
        Dict    =   ReadAnswer(ReDict,html_parser,Dict,k[t].replace('\r',"").replace('\n',"").decode(encoding="utf-8",errors='ignore'),Flag)#使用的是单行模式，所以要去掉\r\n避免匹配失败
        if  Dict['UpdateTime']!='1970-01-01':
            AnswerDictList.append(Dict)
            AnswerList.append(Dict['Questionhref'])
    print   u'第{}页答案抓取成功'.format(Page+1)
    if  RequestDict[Page][1]==False:#将答案链接列表储存于RequesDict中
        RequestDict[Page][0]=AnswerList
        RequestDict[Page][1]=True
    return  

def Login(cursor=None,UserID='mengqingxue2014@qq.com',UserPassword='131724qingxue'):#newCommitTag
    u"""
        *   功能
            *   模拟知乎网页登陆流程，返回登陆header，并将header储存于数据库中
        *   输入
            *   cursor
                *   数据库游标
            *   UserID
                *   登陆名
            *   UserPassword
                *   登陆密码
        *   返回
             *   携带可用cookie的header头
     """
    qc_1    =   ''#初始化
    print   u'开始验证网页能否打开，验证完毕后将开始登陆流程，请稍等。。。'
    header  =   {
                    'Accept'    :   '*/*'                                                                                 
                    ,'Accept-Encoding'   :'gzip,deflate,sdch'
                    ,'Accept-Language'    :'zh,zh-CN;q=0.8,en-GB;q=0.6,en;q=0.4'
                    ,'Connection'    :'keep-alive'
                    ,'Host'    :'www.zhihu.com'
                    ,'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'
                    ,'DNT':'1'
                    ,'User-Agent':'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36\
                     (KHTML, like Gecko) Chrome/34.0.1847.116 Safari/537.36'
                    ,'X-Requested-With':'XMLHttpRequest'
                }
    try :
        ZhihuFrontPage=urllib2.urlopen(u"http://www.zhihu.com")#这里也可能出错#初次打开zhihu.com,获取xsrf信息
    except  urllib2.HTTPError   as e    :
        print   u'服务器错误'
        print   u'错误内容',str(e).decode("utf-8")
        print   u'转为使用旧有PostHeader'
        return  OldPostHeader(cursor=cursor)
    except  urllib2.URLError    as e    :
        print   u'网络错误'
        print   u'错误内容',str(e).decode("utf-8")
        print   u'话说网络链接正常不？'
        print   u'转为使用旧有PostHeader'
        return  OldPostHeader(cursor=cursor)
    try :
        xsrf    =   '_xsrf=' + re.search(r'(?<=name="_xsrf" value=")[^"]*(?="/>)',ZhihuFrontPage.read()).group(0)
        #print   xsrf
    except  AttributeError:
        ErrorReturn(u'xsrf读取失败，程序出现致命故障，无法继续运行。\n错误信息：知乎的登陆验证方式可能已更改，无法在返回的cookie中正则匹配到xsrf，请知乎@姚泽源更新脚本')
    #except  KeyError:#有这个错误？
    #    ErrorReturn( u'知乎没有设置xsrf\n可能登陆流程已修改，请知乎私信@姚泽源更新软件，不胜感激~')

    header['Cookie']    =   xsrf+';l_c=1'
    header['Origin']    =   'http://www.zhihu.com'#妈蛋知乎改登陆方式了这个坑坑了我整整两天！！！   
    header['Referer']   =   'http://www.zhihu.com/'                                                

    print   u'网页验证完毕，开始登陆流程'
    if  UserID  ==  'mengqingxue2014@qq.com':
        UserID,UserPassword =   InputUserNameandPassword()
        AskRemberFlag       =   True
    else    :
        AskRemberFlag       =   False
        print   u'可以通过使用记事本打开setting.ini文件修改用户名与密码来更换登录帐号'
    MaxTryTime  =   0#最多重复三次，三次后自动切换为使用旧有cookie进行登录
    try:
        while   MaxTryTime<3:
            LoginData   =   urllib.quote('{0}&email={1}&password={2}&rememberme=y'\
                                        .format(xsrf,UserID,UserPassword),safe='=&')#编码Post请求
            request     =   urllib2.Request(url='http://www.zhihu.com/login'\
                                            ,data=LoginData,headers=header)
            try :
                buf         =   urllib2.urlopen(request)
            except  urllib2.HTTPError   as e    :#还可能会有403/500错误
                print   u'服务器错误'
                print   u'错误内容',e
                print   u'话说网络链接正常不？'
                print   u'转为使用旧有Header'
                return  OldPostHeader(cursor=cursor)
            except  urllib2.URLError    as e    :
                print   u'网络错误'
                print   u'错误内容',e
                print   u'话说网络链接正常不？'
                print   u'转为使用旧有PostHeader'
                return  OldPostHeader(cursor=cursor)
            if  qc_1    ==  '':
                try :#如果是初次打开网页的话，登陆成功之后会一并返回qc_1与qc_0,都有用
                    qc_1    =   re.search(r'(q_c1=[^;]*)',buf.info()['set-cookie']).group(0)
                except  AttributeError:
                    ErrorReturn(u'qc_1读取失败，程序出现致命故障，无法继续运行。\n错误信息：知乎登陆流程可能已更改，无法在返回的cookie中正则匹配到qc_1，请知乎@姚泽源更新脚本')         
                    qc_1    =   ''
            try:
                qc_0    =   re.search(r'(q_c0=[^;]*)',buf.info()['set-cookie']).group(0)
            except  AttributeError:
                qc_0    =   ''

            header['Cookie']        =  qc_1 +';'  +xsrf+'; l_c=1'+';'+qc_0
            buf_read    = buf.read()#为什么只能读取一次？？？#info可以读取多次
            PostInfo    =   json.loads(buf_read)
            if  PostInfo['errcode']==269:#提示输入验证码#验证码错误是270#登陆成功不返回任何信息，所以会报错，测试一下#也可能是该用户尚未注册
                print   u'抱歉，错误代码269\n知乎返回的错误信息如下:\n-----------------begin---------------------'
                PrintDict(PostInfo)
                print   '------------------end----------------------'
                ErrorReturn(u'表示无法处理这样的错误\n如果是需要输入验证码的话请用网页登陆一次知乎之后再来吧~（注：私人账号在网页上成功登陆一次之后就不会再出现验证码了）')
            else    :
                if  PostInfo['errcode']==270:
                    try     :
                        print   PostInfo['msg']['captcha'].encode('gbk')#win下要编码成gbk，
                        print   u'验证码错误？什么情况。。。'
                        ErrorReturn(u'好了现在需要输入验证码了。。。命令行界面表示显示图片不能。。。\n请用网页登陆一次知乎之后再来吧~（注：私人账号在网页上成功登陆一次之后就不会再出现验证码了）')
                    except  KeyError:
                        print   u'用户名或密码不正确，请重新输入用户名与密码\n附注:知乎返回的错误信息见下'
                        PrintDict(PostInfo)
                        UserID,UserPassword =   InputUserNameandPassword()
                        AskRemberFlag       =   True
                        print   u'再次尝试登陆。。。'
                        MaxTryTime  +=1
                else    :
                    if  MaxTryTime>=3:
                        print   '三次尝试失败，转为使用已有cookie进行登录'
                        return  OldPostHeader(cursor=cursor)
                    print   u'未知错误，尝试重新登陆，请重新输入用户名与密码\n\PS:知乎返回的错误信息:'
                    PrintDict(PostInfo)
                    UserID,UserPassword =   InputUserNameandPassword()
                    AskRemberFlag       =   True
                    print   u'再次尝试登陆。。。'
                    MaxTryTime  +=1
    except  KeyError:
        print   u'登陆成功！'
        print   u'登陆账号:',UserID
        if  AskRemberFlag:
            print   u'请问是否需要记住帐号密码？输入yes记住，输入其它任意字符跳过，回车确认'
            if  raw_input()    ==  'yes'   :
                Setting(ReadFlag=False,ID=UserID,Password=UserPassword)
                print   u'帐号密码已保存,可通过修改setting.ini进行修改密码等操作'#待添加修改帐号密码部分
            else:
                print   u'跳过保存环节，进入下一流程'
        NewHeader   =   (str(datetime.date.fromtimestamp(time.time()).strftime('%Y-%m-%d')),header['Cookie'])#Time和datetime模块需要导入        
        
        SaveDict    =   {}
        SaveDict['Var']     =   'PostHeader'
        SaveDict['Pickle']  =   pickle.dumps(NewHeader)
        SaveToDB(cursor=cursor,NeedToSaveDict=SaveDict,primarykey='Var',TableName='VarPickle')
        return  header
        #提取qc_0,储存之
def OldPostHeader(cursor=None):#可以加一个网络更新cookie的功能#Pass
    u"""
        *   功能
            *   返回一个可用的header头
            *   若数据库中存在，则直接返回数据库中的header
            *   否则返回内嵌在代码里的header头
            *   可以考虑直接把cookie放到服务器上，
                    由服务器自动更新cookie
        *   输入
            *   数据库游标
        *   返回
             *  可用header
             *  若header已过期则直接报错退出
     """
    header  =   {
                    'Accept'    :   '*/*'                                                                                 
                    ,'Accept-Encoding'   :'gzip,deflate,sdch'
                    ,'Accept-Language'    :'zh,zh-CN;q=0.8,en-GB;q=0.6,en;q=0.4'
                    ,'Connection'    :'keep-alive'
                    ,'Host'    :'www.zhihu.com'
                    ,'User-Agent':'Mozilla/5.0 (Windows NT 6.3; WOW64) \
                      AppleWebKit/537.36 (KHTML, like Gecko)\
                      Chrome/34.0.1847.116 Safari/537.36'
                }
                        
    rowcount    =   cursor.execute('select count(Pickle)  from VarPickle where Var="PostHeader"').fetchone()[0]    
    if  rowcount==0:
        List    =   ('2014-05-26', '_xsrf=9747077ec0374d469c91d06f4bf78c4d; q_c1=a5702f2ffc0344ae91e9efc0874012a8|1401117498000|1394290295000; q_c0="NTc1Mjk3OTkxMmM1NzU1N2MzZGQ5ZTMzMzRmNWVlMDR8MW9xU3hPdDF4U29BQlc4Qg==|1401117516|4bccb71dbbdd69c36ee800ef20586a6060ab8559";')#黄中华的cookie
    else:
        List    =   pickle.loads(cursor.execute("select Pickle   from VarPickle  where Var='PostHeader'").fetchone()[0])#这种错误。。。真难发现啊
    recordtime  =   datetime.datetime.strptime(List[0],'%Y-%m-%d').date()
    today       =   datetime.date.today()
    diff        =   30- (today - recordtime).days
    if  diff    >   0:
        print   u'转为使用'+List[0]+u'的登陆记录进行登陆，可能无法读取私人收藏夹。距离该记录过期还有'+str(diff)+u'天，过期后程序将无法继续运行，成功使用账号密码登陆可将记录刷新'
        header['Cookie']    =   List[1]
    else    :
        ErrorReturn(u'账号密码登录&登陆记录已过期\n程序继续无法运行\n请重新运行程序，尝试使用账号密码进行登录。\n倘若一直无法登陆的话请上知乎私信@姚泽源反馈bug,不胜感激')
    return header
def InputUserNameandPassword():#UnitTest
    u"""
        *   功能
            *   引导用户输入知乎帐号密码，在进行简单的正则校验之后返回两个值，第一个为登陆名，第二个是登陆密码
        *   输入
            *   无
        *   返回
             *   UserID,UserPassword
     """
    print   u'请输入您的登陆用户名(知乎注册邮箱)，回车确认'    
    print   u'示例:\n用户名:mengqingxue2014@qq.com\n密码：131724qingxue\nPS:别用这个示例账号。。。登不上。。。囧'
    print   u'请输入用户名,回车确认'
    LoopFlag    =   True
    while   LoopFlag:
        UserID  =   raw_input()
        try :
            re.search(r'\w+@[\w\.]{3,}',UserID).group(0)
        except  AttributeError:
            print   u'话说，输入的账号不规范啊'
            print   u'账号规范：1.必须是正确格式的邮箱\n2.邮箱用户名只能由数字、字母和下划线_构成\n3.@后面必须要有.而且长度至少为3位'
            print   u'范例：mengqingxue2014@qq.com\n5719asd@sina.cn'
            print   u'请重新输入账号，回车确认'
        else:
            LoopFlag    =   False
    print   u'OK,请输入密码，回车确认'
    LoopFlag    =   True
    while   LoopFlag:
        UserPassword  =   raw_input()
        try :
            re.search(r'.{6,}',UserPassword).group(0)#密码中可以有符号
        except  AttributeError:
            print   u'话说，输入的密码不规范啊'
            print   u'密码规范：1.至少6位'
            print   u'范例：helloworldvia27149,9527zaizhihu~'
            print   u'请重新输入密码，回车确认'
        else:
            LoopFlag    =   False
    print   u'Ok，开始发送登陆请求'
    return  UserID,UserPassword
    
def returnConnCursor():#Pass
    u"""
        *   功能
            *   打开ZhihuDateBase数据库，若不存在则直接新建一个
            *   返回数据库连接，游标
        *   输入
            *   无
        *   返回
             *   conn,cursor
     """
    if  os.path.isfile('./ZhihuDateBase.db'):
        conn    =   sqlite3.connect("./ZhihuDateBase.db")
        conn.text_factory = str
        cursor  =   conn.cursor()
    else:
        conn    =   sqlite3.connect("./ZhihuDateBase.db")
        conn.text_factory = str
        cursor  =   conn.cursor()
        cursor.execute("create table VarPickle (Var varchar(255),Pickle varchar(50000),primary key (Var))")
        cursor.execute("create table AnswerInfoTable    ( ID              varchar(255) not Null , Sign            varchar(9000) not Null , AgreeCount      int(11)      not Null ,  QuestionID      varchar(20) not Null , AnswerID        varchar(20) not Null , UpdateTime      date         not Null , CommitCount     int(11)      not Null , QuestionTitle   varchar(1000) not Null , Questionhref    varchar(255) not Null , UserName        varchar(255) not Null ,UserIDLogoAdress varchar(255) not Null, primary key(Questionhref))")#没有数据库就新建一个
        cursor.execute("create  table AnswerContentTable    (AnswerContent   longtext     not Null ,  Questionhref    varchar(255) not Null , primary key(Questionhref))")
        cursor.execute("create  table   CollectionIndex (CollectionID   varchar(50) not Null,Questionhref   varchar(255)    not Null, primary key(CollectionID,Questionhref))")#负责永久保存收藏夹链接，防止丢收藏
        cursor.execute('''
CREATE TABLE IDInfo          (IDLogoAdress  varchar(255) default "http://p1.zhimg.com/da/8e/da8e974dc_m.jpg",ID varchar(255) not Null, Sign  varchar(255) default '',Name varchar(255) default '',Ask varchar(255) default '',Answer int default 0,Post int default 0,Collect int default 0,Edit int default 0,Agree int default 0,Thanks int default 0,Followee int default 0,Follower int default 0,Watched int default 0,primary key(ID))
                ''')
        cursor.execute('create  table   CollectionInfo  (CollectionID varchar(50) not Null,Title varchar(255),Description varchar(1000),AuthorName varchar(255),AuthorID varchar(255),AuthorSign varchar(255),FollowerCount int(20)  not Null   ,primary key(CollectionID))')
        cursor.execute('create  table   TopicInfo       (Title varchar(255),Adress varchar(255),LogoAddress varchar(255),Description varchar(3000),TopicID varchar(50),primary key (TopicID))')
        conn.commit()
    return  conn,cursor
def CatchFrontInfo(ContentText='',Flag=0,Target=''):
    u"""
        *   功能
            *   分析提取首页信息，返回对应的InfoDict
        *   输入
            *   首页文本数据，首页类型标志符，若首页不是用户首页的话需附上目标ID值
                *   最好改进为即使是用户首页也应该输入目标ID，这样的输入才便于标准话
        *   返回
             *  InfoDict，内含所需的信息
                *  改进建议：应对InfoDict进行标准化处理，或者分为4个独立的应用程序进行处理
     """
    html_parser =   HTMLParser.HTMLParser()
    def rTC(text=''):#returnTrueContent
        return  html_parser.unescape(text)


    if  ContentText=='':
        return# 应该raise个错误出去
    print   u'开始读取答案首页信息。。。'
    InfoDict={}
    if  Flag    ==0:
        return  InfoDict
    if  Flag    ==1:#1,ID;2,Collect;3,RoundTable;4,Topic
        ID_Name_Sign                =   re.search(r'(?<=<div class="title-section ellipsis">).*?(?=<div class="body clearfix">)',ContentText).group(0)
        InfoDict['IDLogoAdress']        =   re.search(r'''(?<=src=")http://pic\d\.zhimg\.com/[_\w]{11}\.jpg(?="class="zm-profile-header-img zg-avatar-big zm-avatar-editor-preview")''',ContentText).group(0)#更新页面结构了我去
        InfoDict['ID']                  =   rTC(re.search(r'(?<=href="/people/)[^"]*',ID_Name_Sign).group(0))
        try:
            InfoDict['Sign']            =   rTC(re.search(r'(?<=<span class="bio" title=").*?(?=">)',ID_Name_Sign).group(0)) 
        except  AttributeError:
             InfoDict['Sign']           =   ''
        InfoDict['Name']            =   rTC(re.search(r'(?<=">).*?(?=</a>)',ID_Name_Sign).group(0))
        ##################################
        Ask_Answer_Pst_CoE          =   re.findall(r'(?<=<span class="num">).*?(?=</span></a>)',ContentText)
        InfoDict['Ask']             =   Ask_Answer_Pst_CoE[0]
        InfoDict['Answer']          =   Ask_Answer_Pst_CoE[1]
        InfoDict['Post']            =   Ask_Answer_Pst_CoE[2]
        InfoDict['Collect']         =   Ask_Answer_Pst_CoE[3]
        InfoDict['Edit']            =   Ask_Answer_Pst_CoE[4]
        ##################################
        
        InfoDict['Agree']           =   re.search(r'(?<=<span class="zm-profile-header-user-agree"><span class="zm-profile-header-icon"></span><strong>).*?(?=</strong>)',ContentText).group(0)
        InfoDict['Thanks']          =   re.search(r'(?<=<span class="zm-profile-header-user-thanks"><span class="zm-profile-header-icon"></span><strong>).*?(?=</strong>)',ContentText).group(0)
        ##################################
        Followee_er                 =   re.findall(r'(?<=</span><br /><strong>).*?(?=</strong><label>)',ContentText)
        InfoDict['Followee']        =   Followee_er[0]
        InfoDict['Follower']        =   Followee_er[1]
        ##################################
        
        InfoDict['Watched']         =   re.search(r'(?<=[^>]{1}<strong>).*?(?=</strong>)',ContentText).group(0)
    if  Flag==2:#收藏夹
        InfoDict['CollectionID']    =   Target
        InfoDict['Title']           =   rTC(re.search(r'(?<=<h2 class="zm-item-title zm-editable-content" id="zh-fav-head-title">).*?(?=</h2>)',ContentText).group(0))
        try :
            InfoDict['Title']       =   rTC(re.search(r'(?<=class="icon icon-lock"></i>).*',InfoDict['Title']).group(0))#针对私人收藏夹进一步处理
        except  AttributeError:
            pass
        InfoDict['Description']     =   rTC(re.search(r'(?<=<div class="zm-editable-content" id="zh-fav-head-description">).*?(?=</div>)',ContentText).group(0))              
        AuthorInfoStr               =   re.search('(?<=<h2 class="zm-list-content-title">).*?(?=</div>)',ContentText).group(0)
        InfoDict['AuthorName']      =   rTC(re.search(r'(?<=">).*?(?=</a></h2>)',AuthorInfoStr).group(0))
        InfoDict['AuthorID']        =   re.search(r'(?<=<a href="/people/)[^"]*(?=">)',AuthorInfoStr).group(0)              
        try :
            InfoDict['AuthorSign']  =   rTC(re.search(r'(?<=<div class="zg-gray-normal">).*',AuthorInfoStr).group(0))
        except  AttributeError:
            InfoDict['AuthorSign']  =   ''    
        try :
            InfoDict['FollowerCount']   =   re.search(r'(?<=<div class="zg-gray-normal"><a href="/collection/\d{8}/followers">)\d*?(?=</a>)',ContentText).group(0)                   
        except  AttributeError:
            InfoDict['FollowerCount']   =   0#私密收藏夹没有关注数
    if  Flag==3:#圆桌  
        InfoDict['TableID']         =   Target
        Title_LogoAddress           =   re.search(r'(?<=<h1 class="title">).*?(?=</h1>)',ContentText).group(0)

        InfoDict['Title']           =   rTC(re.search(r'(?<=<strong>).*(?=</strong>)',Title_LogoAddress).group(0))
        InfoDict['Adress']          =   re.search(r'(?<=<a href=")[^"]*',Title_LogoAddress).group(0) #/roundtable/copyright2014
        InfoDict['LogoAddress']     =   re.search(r'(?<=<img src=").*(?=" alt=")',Title_LogoAddress).group(0)                 
        InfoDict['Description']     =   rTC(re.search(r'(?<=<div class="description">).*?(?=</div>)',ContentText).group(0))                 
    if  Flag==4:#Topic
        InfoDict['TopicID']         =   Target
        InfoDict['Title']           =   rTC(re.search(r'(?<=<title>).*?(?=</title>)',ContentText).group(0)[:-12])
        
        InfoDict['Adress']          =   re.search(r'(?<=http://www.zhihu.com).*?(?=">)',ContentText).group(0)#/topic/19793502
        Buf                         =   re.search(r'(?<=<img alt).*?(?=<)',ContentText).group(0)
        InfoDict['LogoAddress']     =   re.search(r'(?<=src=").*?(?=" class="zm-avatar-editor-preview">)',Buf).group(0)                 
        try :
            InfoDict['Description']     =   rTC(re.search(r'(?<=<div class="zm-editable-content" data-editable-maxlength="130" >).*?(?=</div>)',ContentText).group(0))                #正常模式
        except  AttributeError:
            InfoDict['Description']     =   rTC(re.search(r'(?<=<div class="zm-editable-content" data-editable-maxlength="130" data-disabled="1">).*?(?=</div>)',ContentText).group(0))                #话题描述不可编辑
    print   u'首页信息读取成功'
    return  InfoDict

def CreateWorkListDict(PostHeader,TargetFlag,Target):#输入http头、目标代码，目标名，返回首页信息字典与待抓取Request字典#Pass
    u"""
        *   功能
            *   根据传入的目标类型，目标ID，制作待读取的Request列表并返回
            *   后续函数只需要依次读取RequestDict内的元素所对应的网页内容即可
            *   同时在第二个返回值处还会返回必要的首页信息
        *   输入
            *   PostHeader
                *   一个可以打开的Http头字典
                *   用于制作Rqeust字典
            *   TargetFlag
                *   目标类型
            *   Target
                *   目标ID
        *   返回
             *   InfoDict
                *   目标的首页信息
            *   RequestDict
                *   制作完成的Request字典
     """
    if  TargetFlag==1:
        url =   'http://www.zhihu.com/people/'+Target+'/answers?page='          
    else:
        if  TargetFlag==2:
            url =   'http://www.zhihu.com/collection/'+Target+'?page='
        else:
            if  TargetFlag==3:#特殊处理
                #url =   'http://www.zhihu.com/roundtable/'+Target+'/answers'
                #InfoDict    =   CatchFrontInfo(k,TargetFlag)
                #算了不做知乎圆桌了，麻烦
                return
            else:
                if  TargetFlag==4:
                    url =   'http://www.zhihu.com/topic/'+Target+'/top-answers?page='#话题功能尚未测试
                else:
                    ErrorReturn(u'输入内容有误，创建待读取列表失败，在输入中提取到的内容为：\n{}\n,错误代码:{}\n'.format(Target,TargetFlag))
    Request =   urllib2.Request(headers=PostHeader,url=url)
    k       =  ''
    Times    =   0
    while   k==''   and Times<10:
        print   u'正在打开答案首页',url
        k   =   OpenUrl(Request).decode(encoding='utf-8',errors='ignore')#文本内容必须要经过编码，否则会导致搜索时出现故障
        if  k=='':
            print   u'第{}/10次尝试打开答案首页失败，1秒后再次打开'.format(Times+1)
            time.sleep(1)
        Times+=1
    if  k   ==  '':
        ErrorReturn(u'打开答案首页失败，请检查网络连接\n打开失败的网址为'+url)
    k   =   k.replace('\n','').replace('\r','')
    InfoDict    =   CatchFrontInfo(k,TargetFlag,Target)
    MaxPage     =   FetchMaxAnswerPageNum(k)
    RequestDict =   {}
    for No  in  range(MaxPage):#从0开始，不要干从1开始这种反直觉的事
        RequestDict[No]    =   [urllib2.Request(url=url+str(No+1),headers=PostHeader),False]
    return  InfoDict,RequestDict

def returnIndexList(cursor=None,Target='',Flag=0,RequestDict={}):#Pass
    u"""
        *   功能
            *   提取对应于目标值的答案链接列表，并同步进私人电脑中
            *   用于为这些ID创建数据库，避免他们删答案
        *   输入
            *   数据库游标，目标代号，目标类型代码，待处理Reuest字典
        *   返回
             *   目标的索引
     """
    print   u'读取答案成功，正在生成答案索引'
    Index   =   []
    if  Flag==1:
        for t   in  cursor.execute('select Questionhref  from    AnswerInfoTable where ID=? order   by  AgreeCount  desc',(Target,)):
            Index.append(t[0])
    else:
        if  Flag==2:
            for t   in  cursor.execute('select CollectionIndex.Questionhref  from    CollectionIndex,AnswerInfoTable    where CollectionIndex.CollectionID=?    and CollectionIndex.Questionhref=AnswerInfoTable.Questionhref   order   by  AnswerInfoTable.AgreeCount  desc',(Target,)):
                Index.append(t[0])
        else:
            for t   in  RequestDict:
                try:
                    for i   in   RequestDict[t][0]:
                        Index.append(i)
                except  TypeError:#当抓取不成功时貌似不会弹AttributeError，所以换成直接检测TypeError
                    pass
                    
    print   u'答案索引生成完毕，共有{}条答案链接'.format(len(Index))
    return  Index
def SaveToDB(cursor=None,NeedToSaveDict={},primarykey='',TableName=''):#Pass
    u"""
        *   功能
            *   提供一个简单的数据库储存函数，按照NeedToSaveDict里的设定，将值存入键所对应的数据库中
            *   表与主键由TableName   ，  primarykey指定
            *   注意，本函数不进行提交操作
        *   输入
            *   cursor
                *   数据库游标
            *   NeedToSaveDict
                *   需要存入数据库中的键值对
                *   键为数据库对应表下的列名，值为列值
            *   primarykey
                *   用于指定主键
            *   TableName
                *   用于指定表名
        *   返回
             *   无
     """
    rowcount    =   cursor.execute('select count({}) from {} where {} = ?'.format(primarykey,TableName,primarykey),(NeedToSaveDict[primarykey],)).fetchone()[0]
    SQL1    =   'insert into '+TableName+' ('
    SQL2    =   ' ) values ( '
    SQLTuple=   []
    sql1    =   'update '+TableName+' set '
    for t   in  NeedToSaveDict:
        SQL1+=t+','
        SQL2+='?,'
        SQLTuple.append(NeedToSaveDict[t])
        sql1+=t+'=?,'
    if  rowcount==0:
        #insert
        cursor.execute(SQL1[:-1]+SQL2[:-1]+')',tuple(SQLTuple))
    else:
        #update
        SQLTuple.append(NeedToSaveDict[primarykey])
        cursor.execute(sql1[:-1]+' where '+primarykey+'= ?',tuple(SQLTuple))




def ZhihuHelp():
    u"""
        *   主程序不解释
     """
    conn,cursor =   returnConnCursor()
    ErrorReportText(flag=False)#初始化错误报告文件
    Mkdir(u'./知乎答案集锦')
    try:
        ReadList    =   open("./ReadList.txt","r")
    except  IOError as e:
        print   e
        ErrorReturn(u'程序所在的目录里好像没有ReadList.txt这个文件，先手工新建一个吧')
    ReSettingFlag=True
    if  os.path.isfile('setting.ini'):
        try :
            Setting()
        except  :
            pass
        else:
            print   u'检测到有设置文件，是否直接使用之前的设置？(帐号、密码、最大线程数)'
            print   u'直接点按回车使用之前设置，敲入任意字符后点按回车进行重新设置'
            if  raw_input()=='':
                ReSettingFlag=False
    if  ReSettingFlag:
        PostHeader  =   Login(cursor=cursor)#
        MaxThread   =   20
        print   u'ZhihuHelp热身中。。。\n开始设定最大允许并发线程数\n线程越多速度越快，但线程过多会导致知乎服务器故障无法打开网页读取答案失败，默认最大线程数为20\n请输入一个数字（1~50），回车确认'
        MaxThread   =   setMaxThread()
        PicDownload =   SetPicDownload()
        Setting(ReadFlag=False,MaxThread=str(MaxThread),PicDownload=str(PicDownload))
    else:
        ID,Password,MaxThread,PicDownload   =   Setting()
        #print   "PicDownload=",PicDownload,"Type=",type(PicDownload)
        print   u'配置信息读取完毕'
        print   u'登录帐号\t:\t{}\n登录密码\t:\t{}\n最大线程数\t:\t{}\n图片下载模式\t:\t'.format(ID,Password,MaxThread),
        if  not PicDownload:
            print   u'无图模式'
        elif    PicDownload==1:
            print   u'标清图模式'
        else:
            print   u'高清图模式'
        PostHeader  =   Login(UserID=ID,UserPassword=Password,cursor=cursor)#ID,Password在这里进行记录
    for TargetUrl in    ReadList:
        print   u'开始识别目标网址'
        TargetUrl           =   TargetUrl.replace('\n','').replace('\r','')
        TargetFlag,Target   =   ChooseTarget(TargetUrl)
        if  TargetFlag==0:
            print   u'识别目标网址失败，原网址:',TargetUrl,u'识别结果：',Target
            continue
        try :
            InfoDict,RequestDict=   CreateWorkListDict(PostHeader=PostHeader,TargetFlag=TargetFlag,Target=Target)
        except  IOError as e:
            print   e
            ErrorReportText(Info=u'读取用户信息出错\t:\t'+str(e))
            continue
        except  ValueError as   e   :
            print   e
            print   u'404网页错误或服务器拒绝访问\nPS:话说那个链接是私人收藏夹么？下载私人收藏夹需要用自己的帐号登陆知乎助手才行。'
            ErrorReportText(Info=u'读取用户信息出错\t:\t'+str(e))
            continue
        print   u'开始抓取答案'
        ThreadWorker(cursor=cursor,MaxThread=MaxThread,RequestDict=RequestDict,Flag=TargetFlag)
        if  TargetFlag==2:
            SaveCollectionIndexIntoDB(RequestDict=RequestDict,CollectionID=Target,cursor=cursor)
        conn.commit()
        IndexList   =   returnIndexList(cursor=cursor,Target=Target,Flag=TargetFlag,RequestDict=RequestDict)
        #将IndexList存在数据库中，方便制作电子书
        SaveToDBDict={}
        SaveToDBDict['Var']   =     TargetUrl
        SaveToDBDict['Pickle']=     pickle.dumps(IndexList)
        SaveToDB(cursor=cursor,NeedToSaveDict=SaveToDBDict,primarykey='Var',TableName='VarPickle')
        conn.commit()
        #直接储存InfoDict
        SaveToDBDict={}
        SaveToDBDict['Var']   =     TargetUrl+'InfoDict'
        SaveToDBDict['Pickle']=     pickle.dumps(InfoDict)
        SaveToDB(cursor=cursor,NeedToSaveDict=SaveToDBDict,primarykey='Var',TableName='VarPickle')
        conn.commit()
        
        print   u'开始生成电子书'
        EpubBuilder(MaxThread,[TargetUrl,],PicDownload)#一本一本的做，便于发现问题
    print   u'恭喜，所有电子书制作完毕'
    print   u'点按回车退出'
    raw_input()

if  __name__ == '__main__' :
    try:
        pass
        CheckUpdate()
        ZhihuHelp()
    except :
        info=sys.exc_info()  
        print   u'程序异常退出，快上知乎上@姚泽源反馈下bug\n或者把bug和ReadList.txt一块发给yaozeyuan93@gmail.com也行，谢谢啦~\n错误信息如下:\n'
        print info[0],":",info[1]
        print   u'错误信息显示完毕\n点按回车退出'
        raw_input()
else:
    print   "Test Mode"
    ZhihuHelp()
