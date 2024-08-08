import win32com.client
import subprocess
import time
import psutil
import pandas as pd


def check_and_open_sap(server_name:str, id:str, pw:str, windows:int=3):
    """
        SAP이 켜져있는지 확인하고,
        켜져있으면 켜져있는 session을 반환하고
        꺼져있으면 켠 뒤 session을 반환한다
        window로 지정한 수만큼 창을 켤 수 있으며 미지정시 3개를 킨다

        ex) check_sap_available('SEP', 'kibok.park', 'aaaa123456*',3)
    """
    # 실수로 windows에 str입력한 경우 대응
    windows = int(windows)
    # SAP이 켜져있는지 확인하고 아니면 킨다.
    sap_process_count = 0
    for proc in psutil.process_iter():
        if 'saplogon.exe' in str(proc.name()):
            sap_process_count += 1
    if sap_process_count == 0:
        subprocess.Popen("C:\\Program Files (x86)\\SAP\\FrontEnd\\SapGui\\saplogon.exe")
        while True:
            process_list = [str(proc.name()) for proc in psutil.process_iter()]
            if 'saplogon.exe' in process_list:
                break

    rotEntry = win32com.client.GetObject("SAPGUI")
    guiApp = rotEntry.GetScriptingEngine
    connection_dict = {}
    session_list = []

    # SEP, DEP 등이 켜져있는지 확인하고 맞는 서버가 없으면 켠다(Connection할당)
    if guiApp.Connections.Count > 0:
        for server in guiApp.Connections:
            connection_dict[server.Children(0).info.systemname] = server
        
        connection = connection_dict.get(server_name) 
        if connection is  None:
            connection = sap_login(guiApp, server_name, id, pw)                
    else:
        connection = sap_login(guiApp, server_name, id, pw)
    
    # 켜진 창의 수를 세고 필요한 만큼 추가로 생성한다
    windowQtyToOpen = windows - connection.Children.Count
    session = connection.Children(0)
    for i in range(windowQtyToOpen):
        session.createSession()
        time.sleep(1)
    
    # 켜진 session들을 모아서 리턴한다 (요청한 창보다 더 많이 켜져있으면 함께 리턴)
    for i in range(connection.Children.Count):
        session_list.append(connection.Children(i))
    return session_list


def sap_login(guiApp, server_name:str, id:str, pw:str):
    """
        SAP을 입력한 모듈(SEP 등)에 맞추어 켠다
        앞서 win32com으로 받아둔 개체가 필요함

        ex)
        rotEntry = win32com.client.GetObject("SAPGUI")
        guiApp = rotEntry.GetScriptingEngine

        sap_login(guiApp, server_name, id, pw)
    """
    connection = guiApp.OpenConnection(server_name, True)
    session = connection.Children(0)
    session.findById("wnd[0]/usr/txtRSYST-BNAME").Text = id  
    session.findById("wnd[0]/usr/pwdRSYST-BCODE").Text = pw
    session.findById("wnd[0]/tbar[0]/btn[0]").press()
    #팝업 끄기
    if session.ActiveWindow.Name == "wnd[1]":
        if "USEP Information" in session.findById("wnd[1]").Text:
            session.findById("wnd[1]").Close()  #GERP팝업닫기
        elif "Logon Information" in session.findById("wnd[1]").Text:
            session.findById("wnd[1]").Close()  #GERP팝업닫기
    return connection


def start_menu_with_tcode(session, tcode:str)->None:
    if session.info.Transaction == "SESSION_MANAGER":
        session.StartTransaction(tcode)
    else:
        session.EndTransaction()
        session.StartTransaction(tcode)

def loop_tcode(session, tcode:str)->None:
    if session.info.Transaction == "SESSION_MANAGER":
        session.findById("wnd[0]/tbar[0]/okcd").Text = tcode
        session.findById("wnd[0]").sendVKey(0)
    else:
        session.findById("wnd[0]").sendVKey(3)

def error_handler_pi(session, error_txt:str)->bool:
    if session.ActiveWindow.Name == "wnd[1]":
        if error_txt in session.findById("wnd[1]/usr/txtMESSTXT1").Text:
            session.findById("wnd[1]/tbar[0]/btn[0]").press()   # 메시지 창끄기
            return True    
        
def chk_exist_pi_lc(session, pi_name:str)->bool:
    start_menu_with_tcode(session, 'ZSDP10200_B')
    session.findById("wnd[0]/usr/txtZTSDP00130-ZLC_NO").text = pi_name
    session.findById("wnd[0]").sendVKey(0)
    if session.findById("wnd[0]/sbar").Text != f'L/C number {pi_name} cannot be found':
        return True

def input_pi_lc(session, lc_org:int, pi_info:list[str], date:list[str], main_info:list[str,bool], port_and_address_txt:list[str], is_local:bool=False)->None:
    '''
    # 입력예시 
    input_pi_lc(session, lc_org=1, 
                pi_info=['IATEC-0001','2417202'], # PI이름, 거래선코드
                date=['2023.01.01','2023.01.15','2023.01.15'], # Open/Last/Expiry date
                main_info=['USD',100000,'OA14','CIP','HANOI',True, False], # CUR, AMOUNT, PAYMENT, INCO, INCOTEXT, PARTIAL, TRANSHIP
                port_and_address_txt = [['VNHAN','ARBUE', # POL, FDEST
                                        [],               # POL TEXT, FDEST TEXT
                                        {'applicant':'applicant address\napplicant address', # 항목별 세부주소
                                        'seller':'seller address\nseller',
                                        'notify':'notify address\nnotify',
                                        'consignee':'consignee address\nconsignee',
                                        'shippingmark':'shippingmark\nshippingmark'}
                                        ],
                                        # 주소가 여러개인 경우 리스트형으로 추가한다
                                        ['VNSGN','ARBUE',
                                        ['Vietnam,Saigonn','Argen,BUEEEE'],
                                        {'applicant':'applicant address\napplicant address2',
                                        'seller':'seller address\nseller2',
                                        'notify':'notify address\nnotify2',
                                        'consignee':'consignee address\nconsignee2',
                                        'shippingmark':'shippingmark\nshippingmark2'}
                                            ]
                                        ]
    )
    '''
    # 전처리
    pol1 = []
    pol2 = []
    fdest1 = []
    fdest2 = []
    full_portname = [] # Null허용
    address_txt = []

    for each_address in port_and_address_txt:
        pol1.append(each_address[0][:2])
        pol2.append(each_address[0][2:])
        fdest1.append(each_address[1][:2])
        fdest2.append(each_address[1][2:])
        full_portname.append(each_address[2])
        address_txt.append(each_address[3]) 
           
    date_open = date[0].replace('-','.')
    date_lastship = date[1].replace('-','.')
    date_expire = date[2].replace('-','.')

    data_cur, data_amount, data_payment, data_inco, data_incotext, chk_partial, chk_tranship = main_info
    name_pi, customer = pi_info

    # t-code진입 후 입력 시작
    start_menu_with_tcode(session, 'ZSDP10200_A') 

    # page1
    session.findById("wnd[0]/usr/ctxtZTSDP00130-ZLCORG").Text = lc_org     # LC ORG 입력(1=SET)
    session.findById("wnd[0]").sendVKey(0)   #엔터

    if is_local:
        session.findById("wnd[0]/usr/radLLCMARK_03").select() # lOCAL 선택

    session.findById("wnd[0]/usr/ctxtZTSDP00130-ZBUYER").Text = customer   #거래선 코드
    session.findById("wnd[0]/usr/txtZTSDP00130-ZLC_NO").Text = name_pi          #PI및LC이름
    session.findById("wnd[0]/usr/ctxtZTSDP00200-LCOUNTRY").Text = pol1[0]       #Loading Port국가
    session.findById("wnd[0]/usr/ctxtZTSDP00200-POL").Text = pol2[0]      #Loading Port포트
    session.findById("wnd[0]/usr/ctxtZTSDP00200-COUNTRY").Text = fdest1[0]   #Final Dest국가
    session.findById("wnd[0]/usr/ctxtZTSDP00200-FINDEST").Text = fdest2[0]  #Final Dest포트

    session.findById("wnd[0]").sendVKey(0)   #엔터

    
    # 정의된 에러가 있으면 창을 끄고, 등록불가한 이유는 메인화면으로 간다
    if error_handler_pi(session, 'already exists') or error_handler_pi(session, "L/C Number can not include '_'."):
        session.findById("wnd[0]").sendVKey(3)              # 뒤로가기(LC org 창으로)
        session.findById("wnd[0]").sendVKey(3)              # 뒤로가기(메인화면으로)
        return
    
    # page2
    error_handler_pi(session, 'Only Sales Area B001-20-Z1 of 5292812 were deleted')
    session.findById("wnd[0]/usr/ctxtZTSDP00130-ZCURR").Text = data_cur       # CURRENCY
    session.findById("wnd[0]/usr/txtZTSDP00130-ZOP_AMT").Text = data_amount   # AMOUNT
    session.findById("wnd[0]/usr/ctxtZTSDP00130-ZTERM").Text = data_payment   # PAYMENT TERM
    session.findById("wnd[0]/usr/ctxtZTSDP00130-ZINCO").Text = data_inco      # INCOTERMS
    session.findById("wnd[0]/usr/ctxtZTSDP00130-ZOP_DT").Text = date_open     # OPENING DATE
    session.findById("wnd[0]/usr/ctxtZTSDP00130-ZSP_DT").Text = date_lastship # SHIPMENT DATE
    session.findById("wnd[0]/usr/ctxtZTSDP00130-ZVAL_DT").Text = date_expire  # EXPIRY DATE
    session.findById("wnd[0]").sendVKey(0)   # 엔터(인코텀즈 텍스트 입력전에 한번 엔터를 쳐야함)
    error_handler_pi(session, 'Only Sales Area B001-20-Z1 of 5292812 were deleted')
    #if data_incotext is not None:
    if data_incotext != '':
        session.findById("wnd[0]/usr/txtZTSDP00130-ZINCO_DESC").Text = data_incotext  # INCO TEXT
    
    if chk_partial is True or chk_partial == 'O':
        session.findById("wnd[0]/usr/chkZTSDP00130-ZPS_TAG").Selected = True    # PARTIAL ALLOWED
    elif chk_partial is None or chk_partial == 'X':
        session.findById("wnd[0]/usr/chkZTSDP00130-ZPS_TAG").Selected = False   # PARTIAL NOT ALLOWED

    if chk_tranship is True or chk_tranship == 'O':
        session.findById("wnd[0]/usr/chkZTSDP00130-ZTS_TAG").Selected = True    # TRANSHIP ALLOWED
    elif chk_tranship is None or chk_tranship == 'X':
        session.findById("wnd[0]/usr/chkZTSDP00130-ZTS_TAG").Selected = False   # TRANSHIP NOT ALLOWED

    session.findById("wnd[0]").sendVKey(11)  #저장
    session.findById("wnd[1]/usr/btnSPOP-OPTION1").press()    # SAVE? YES

    #if (session.ActiveWindow.Name = "wnd[1]"):
        

    session.findById("wnd[1]/usr/btnSPOP-OPTION2").press()   # CREATE ITEM? NO

    # page3
    session.findById("wnd[0]/tbar[1]/btn[13]").press()    #기존입력값 삭제(Clear screen)

    # NERP의 index는 1부터 시작
    # address의 인덱스 구성 : SAP식별주소, 줄 제한, 1번째줄 글자제한, 나머지줄 글자제한
    address_idx = {'applicant':{'sap_addr':'wnd[0]/usr/txtZTSDP00200-ZBUY_NM','line_limit':4,'1st_line_limit':35, 'other_line_limit':50},
                   'seller':{'sap_addr':'wnd[0]/usr/txtZTSDP00200-ZSLER','line_limit':4,'1st_line_limit':35, 'other_line_limit':50},
                   'notify':{'sap_addr':'wnd[0]/usr/txtZTSDP00200-ZNOTI','line_limit':5,'1st_line_limit':35, 'other_line_limit':50},
                   'consignee':{'sap_addr':'wnd[0]/usr/txtZTSDP00200-ZCONS','line_limit':6,'1st_line_limit':35, 'other_line_limit':50},
                   'shippingmark':{'sap_addr':'wnd[0]/usr/txtZTSDP00200-ZSHMK','line_limit':10,'1st_line_limit':35, 'other_line_limit':35}
                   }
    
    if len(full_portname) == 0:
        pass
    else:
        if full_portname[0] != []:
            session.findById("wnd[0]/usr/txtZTSDP00200-ZPOL_ADR").Text = full_portname[0][0]
            session.findById("wnd[0]/usr/txtZTSDP00200-ZFD_ADR1").Text = full_portname[0][1]

    #입력부분 확인필요!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    for label in address_idx.keys():
        temp_address = address_txt[0][label].split('\n')
        for i, each_line in enumerate(temp_address):
            session.findById(address_idx[label]['sap_addr'] + str(i + 1)).Text = each_line

    session.findById("wnd[0]").sendVKey(11)                   #저장
    session.findById("wnd[1]/usr/btnSPOP-OPTION1").press()    # SAVE?  YES

    if len(address_txt) == 1:
        session.findById("wnd[1]/usr/btnSPOP-OPTION2").press()    # ADDITIONAL PORT? NO
    else:
        for i in range(1,len(address_txt)):
            session.findById("wnd[1]/usr/btnSPOP-OPTION1").press()    # ADDITIONAL PORT? YES
            # 2번째것부터 입력 시작
            session.findById("wnd[0]/usr/ctxtZTSDP00200-LCOUNTRY").Text = pol1[i]       #Loading Port국가
            session.findById("wnd[0]/usr/ctxtZTSDP00200-POL").Text = pol2[i]      #Loading Port포트
            session.findById("wnd[0]/usr/ctxtZTSDP00200-COUNTRY").Text = fdest1[i]   #Final Dest국가
            session.findById("wnd[0]/usr/ctxtZTSDP00200-FINDEST").Text = fdest2[i]  #Final Dest포트
            session.findById("wnd[0]/tbar[1]/btn[17]").press()   #시프트 + 엔터

            session.findById("wnd[0]/tbar[1]/btn[13]").press()    #기존입력값 삭제(Clear screen)

            if full_portname[i] is not None or full_portname[0] == '':
                session.findById("wnd[0]/usr/txtZTSDP00200-ZPOL_ADR").Text = full_portname[i][0]
                session.findById("wnd[0]/usr/txtZTSDP00200-ZFD_ADR1").Text = full_portname[i][1]    

            for label in address_idx.keys():
                temp_address = address_txt[i][label].split('\n')
                for i, each_line in enumerate(temp_address):
                    session.findById(address_idx[label]['sap_addr'] + str(i + 1)).Text = each_line

            session.findById("wnd[0]").sendVKey(11)                   #저장
            session.findById("wnd[1]/usr/btnSPOP-OPTION1").press()    # SAVE?  YES

            if i == len(address_txt)-1: 
                session.findById("wnd[1]/usr/btnSPOP-OPTION2").press()    # ADDITIONAL PORT? NO
                break

# page4 (인코텀즈 기준 보험조건인 경우에만 사용)
    if data_inco in ['CIF','CIP','DDU', 'DAP','DDP']:
        session.findById("wnd[0]/usr/chkGT_ITAB_ZEI09-SURVEY_CK").Selected = True   # Claim check 체크
        session.findById("wnd[0]").sendVKey (11)                  # 저장
        session.findById("wnd[1]/usr/btnSPOP-OPTION1").press()    # SAVE? YES
        session.findById("wnd[1]/tbar[0]/btn[0]").press()         # Successfully saved data (체크해서 창끄기)


def nego_history_download(session, local_select:str, nego_criteria:list[str], down_path:str)->None:
    """
        nego 다운로드 할때 사용
        local_select : 'O' 또는 'X' 입력
        nego_criteria : 리스트 안에 묶어서 입력 [companycode, nego_org, date_start, date_end]

        ex) nego_history_download(session, 'O', ['C100', 1, date_start,date_end], 'C:\TEMP')
    """
    companycode, nego_org, date_start, date_end = nego_criteria
    module_name = session.info.systemname
    down_filename = f'NEGO_{companycode}_{date_start}-{date_end}_{module_name}_local_{local_select}_negoorg_{nego_org}.xls'

    if local_select == 'O':
        local_case = False
    elif local_select == 'X':
        local_case = True

    start_menu_with_tcode(session, 'ZRSDP63240')

    session.findById("wnd[0]/usr/radP_ALL").Select() # Transfer Trade ALL

    session.findById("wnd[0]/usr/chkCB_OPT1").Selected = local_case # Except Local

    session.findById("wnd[0]/usr/ctxtP_BUKRS").Text = companycode
    session.findById("wnd[0]/usr/ctxtSO_ZNGOR-LOW").Text = nego_org
    session.findById("wnd[0]/usr/ctxtNGO_DAT-LOW").Text = date_start
    session.findById("wnd[0]/usr/ctxtNGO_DAT-HIGH").Text = date_end
    session.findById("wnd[0]/usr/ctxtCNF_DAT-LOW").Text = date_start
    session.findById("wnd[0]/usr/ctxtCNF_DAT-HIGH").Text = date_end
    session.findById("wnd[0]").sendVKey (8)

    if session.findById("wnd[0]/sbar").Text == "Data not found.":
        return 0

    session.findById("wnd[0]/shellcont/shell/shellcont/shell").pressToolbarButton("EXDL")
    session.findById("wnd[1]/usr/ctxtDY_PATH").Text = down_path
    session.findById("wnd[1]/usr/ctxtDY_FILENAME").Text = down_filename
    session.findById("wnd[1]/tbar[0]/btn[11]").press()
    session.findById("wnd[0]").sendVKey (3)

def pouch_download(session, pouch_criteria:list[str], down_path:str)->None:
    """
        Pouch 다운로드에 사용
        pouch_criteria : list로 묶어서 사용 [companycode, date_start, date_end, knoxid]

        ex) pouch_download(session, ['C100',date_start,date_end,''], 'C:\TEMP')
    """
    companycode, date_start, date_end, knoxid = pouch_criteria
    module_name = session.info.systemname
    down_filename = f'POUCH_{module_name}_{companycode}_{date_start}-{date_end}{knoxid}.xlsx'

    #T-CODE 진입
    start_menu_with_tcode(session, 'ZLSDP63040A')

    # ERP 입력(고정)
    session.findById("wnd[0]/usr/ctxtS_BUKRS-LOW").Text = companycode
    session.findById("wnd[0]/usr/ctxtS_PDAT-LOW").Text = date_start
    session.findById("wnd[0]/usr/ctxtS_PDAT-HIGH").Text = date_end
    session.findById("wnd[0]/usr/txtS_CR_ID-LOW").Text = knoxid
    # ERP필수조건 선택(고정)
    session.findById("wnd[0]/usr/radP_B").Select()    #Trans type All
    session.findById("wnd[0]/usr/radP_D").Select()    #Express NO All
    session.findById("wnd[0]/usr/radP_E").Select()    #Express CO All
    session.findById("wnd[0]/usr/radP_A").Select()    #Customer Type All
    session.findById("wnd[0]/usr/radP_C1").Select()   #Sample Yes
    session.findById("wnd[0]/usr/ctxtS_VKORG-LOW").Text = ""    #SORG삭제
    session.findById("wnd[0]").sendVKey (8) #조회

    # 조회결과가 없으면 종료
    if  session.findById("wnd[0]/sbar").Text == 'No matching data found':
        return '조회 결과 없음 (No matching data found)'

    # 엑셀 다운로드
    session.findById("wnd[0]/usr/cntlG_CONTAINER/shellcont/shell").pressToolbarContextButton("&MB_EXPORT")
    session.findById("wnd[0]/usr/cntlG_CONTAINER/shellcont/shell").selectContextMenuItem("&XXL")

    session.findById("wnd[1]/tbar[0]/btn[0]").press()
    session.findById("wnd[1]/usr/ctxtDY_PATH").text = down_path
    session.findById("wnd[1]/usr/ctxtDY_FILENAME").text = down_filename
    session.findById("wnd[1]/tbar[0]/btn[11]").press()

    return f'조회 완료 ({down_filename})'

def down_billing_detail(session, companycd, date_start, date_end, down_path, org_codes)->None:
    start_menu_with_tcode(session, 'ZRLED50501')

    # Input madatory first
    session.findById("wnd[0]/usr/ctxtSO_BUKRS-LOW").text = companycd
    session.findById("wnd[0]/usr/ctxtSO_VKORG-LOW").text = org_codes[0]
    session.findById("wnd[0]/usr/ctxtSO_FKDAT-LOW").text = date_start
    session.findById("wnd[0]/usr/ctxtSO_FKDAT-HIGH").text = date_end

    # Input other criteria
    session.findById("wnd[0]/usr/btn%_SO_VKORG_%_APP_%-VALU_PUSH").press()
    session.findById("wnd[1]/tbar[0]/btn[16]").press() # Delete
    pd.DataFrame(org_codes).to_clipboard(index=False, header=False)
    session.findById("wnd[1]/tbar[0]/btn[24]").press() # Paste
    session.findById("wnd[1]").sendVKey(8)

    session.findById("wnd[0]/tbar[1]/btn[8]").press()

    # Setting Download
    module_name = session.info.systemname
    down_filename = f"Billing Detail Download_{module_name}_{date_start}-{date_end}.XLS"
    session.findById("wnd[1]/usr/ctxtDY_PATH").text = down_path
    session.findById("wnd[1]/usr/ctxtDY_FILENAME").text = down_filename
    session.findById("wnd[1]/tbar[0]/btn[11]").press()

    return f'조회 완료 ({down_filename})'


if __name__ == '__main__':
    pass
