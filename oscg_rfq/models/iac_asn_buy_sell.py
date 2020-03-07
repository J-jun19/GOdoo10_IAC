# -*- coding: utf-8 -*-
import pytz
import time
import odoo
from datetime import datetime,timedelta
from odoo import models, fields, api,odoo_env
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import pdb
from functools import wraps
from odoo.odoo_env import odoo_env
import  traceback
import threading
import traceback, logging, types,json
_logger = logging.getLogger(__name__)

class iacASN(models.Model):
    _inherit = 'iac.asn'
    buy_sell_asn_id = fields.Many2one('iac.asn.buy.sell','Buy Sell ASN')

class iacASNLine(models.Model):
    _inherit = 'iac.asn.line'
    buy_sell_asn_line_id = fields.Many2one('iac.asn.line.buy.sell','Buy Sell ASN Line')
    buy_sell_asn_id = fields.Many2one('iac.asn.buy.sell','Buy Sell ASN')

class iacAsnBuySell(models.Model):
    _name = "iac.asn.buy.sell"
    _order = "id desc"

    vendor_code = fields.Char("VENDOR_CODE")
    vendor_asn = fields.Char("VENDOR_ASN")
    asn_key=fields.Char("ASN Key")#vendor_code+vendor_asn
    state = fields.Selection([('draft','Draft'),
                          ('done','Done'),
                          ('validate_success','Validate Success'),
                          ('validate_fail','Validate Fail'),
                          ('rule_fail','Rule Fail'),
                          ('rule_success','Rule Success'),
                          ('asn_create_fail','Asn Create Fail'),
                          ('asn_create_success','Asn Create Success'),
                          ('sap_fail','Send SAP Fail')
                         ],default='draft',string='status')
    note = fields.Text('Text')

    asn_id = fields.Many2one('iac.asn',string='ASN')
    plant_id = fields.Many2one('pur.org.data',string='Plant Info')
    vendor_id = fields.Many2one('iac.vendor',string='Vendor Info')
    err_msg = fields.Text('Error Message')
    sap_flag=fields.Selection([('Y','YES'),('N','NO')],string="Send To SAP Flag",default="N")
    line_ids=fields.One2many('iac.asn.line.buy.sell','buy_sell_asn_id','Buy Sell Asn Line Info')
    storage_location = fields.Char('Storage Location')
    id = fields.Char('ID')
    create_date = fields.Datetime('Create Time')

    @api.model
    def load_buy_sell_asn_data(self):
        """
        从SAP系统接口获取BUY & SELL ASN数据,并且存储到本地表中
        :return:
        """
        rpc_result, rpc_json_data = self.env['iac.asn'].sap_rpc_get('ODOO_ASN_007')
        #rpc_result=True
        #rpc_json_object={
        #    "Message" : {
        #    "Status" : "Y",
        #    "Message" : "success"
        #    },
        #    "Document" : {
        #        "ITEM" : [
        #            {
        #                "VENDOR_CODE" : "630043",
        #                "VENDOR_ASN" : "9300123456",
        #                "VENDOR_ASN_ITEM" : "1",
        #                "PO_NO" : "4501154752",
        #                "PO_LINE_NO" : "00010",
        #                "PART_NO" : "111BRB224106",
        #                "QTY" : "13",
        #            }
        #        ]
        #    }
        #}
        #rpc_json_data={}
        #rpc_json_data["rpc_callback_data"]=rpc_json_object

        if rpc_result:
            item_list = rpc_json_data.get("rpc_callback_data").get('Document').get('ITEM')
            asn_line_vals_map={}
            asn_vals_map={}
            #记录本次资料的所有vendor
            vendor_list = []

            #处理ASN 分组问题
            for item_val in item_list:
                #line.document_line_erp_id.zfill(5)
                #对存入buy_sell 的po_line_no进行补5位0处理
                po_line_no=str(int(item_val.get("PO_LINE_NO")))
                po_line_no=po_line_no.zfill(5)
                vendor_list.append(item_val.get("VENDOR_CODE"))
                buy_sell_asn_val={
                    "vendor_code":item_val.get("VENDOR_CODE"),
                    "vendor_asn":item_val.get("VENDOR_ASN"),
                    "vendor_asn_item":str(int(item_val.get("VENDOR_ASN_ITEM"))),
                    "po_no":item_val.get("PO_NO"),
                    "po_line_no":po_line_no,
                    "part_no":item_val.get("PART_NO"),
                    "qty":item_val.get("QTY"),
                }

                asn_key=buy_sell_asn_val.get("vendor_code")+buy_sell_asn_val.get("vendor_asn")
                if asn_key not in asn_line_vals_map:
                    asn_line_val_list=[]
                    asn_line_val_list.append(buy_sell_asn_val)
                    asn_line_vals_map[asn_key]=asn_line_val_list

                    asn_vals={
                        "vendor_asn":buy_sell_asn_val["vendor_asn"],
                        "vendor_code":buy_sell_asn_val["vendor_code"],
                        "asn_key":asn_key
                    }
                    asn_vals_map[asn_key]=asn_vals
                else:
                    asn_line_val_list=[]
                    asn_line_val_list=asn_line_vals_map[asn_key]
                    asn_line_val_list.append(buy_sell_asn_val)


            #筛选掉重复vendor
            vendor_list = list(set(vendor_list))
            for vendor_code in vendor_list:
                vendor_id = self.env['iac.vendor'].search([('vendor_code','=',vendor_code)]).id
                self._cr.execute("insert into iac_supplier_key_action_log(action_type,vendor_id,create_date,write_date) values(%s,%s,%s,%s)",('Vendor Create ASN',vendor_id,datetime.now(),datetime.now()))
                self.env.cr.commit()
            #开始创建分组后的buy sell asn 数据
            for asn_key in asn_line_vals_map:
                #判断asn是否已经从接口获取到,已经获取到的不再新建
                asn_buy_sell=self.env["iac.asn.buy.sell"].search([('asn_key','=',asn_key)])

                #判断asn_buy_sell header是否存在
                if asn_buy_sell.exists():
                    #重置header 状态能够被job再次处理
                    asn_buy_sell.write({"sap_flag":"N","state":"draft"})
                    self.env.cr.commit()

                    #获取到当前asn的全部asn_line_list
                    asn_line_vals_list=asn_line_vals_map.get(asn_key)
                    for asn_line_vals in asn_line_vals_list:
                        domain=[('vendor_asn','=',asn_line_vals.get("vendor_asn"))]
                        domain+=[('vendor_asn_item','=',asn_line_vals.get("vendor_asn_item"))]
                        domain+=[('buy_sell_asn_id','=',asn_buy_sell.id)]
                        asn_line_buy_sell=self.env["iac.asn.line.buy.sell"].search(domain,limit=1)
                        #可能存在补充asn_line 的情况,不存在asn_line的情况下进行创建
                        if not asn_line_buy_sell.exists():
                            asn_line_vals["buy_sell_asn_id"]=asn_buy_sell.id
                            asn_line_vals["sap_flag"]="N"
                            asn_line_vals["state"]="draft"
                            self.env["iac.asn.line.buy.sell"].create(asn_line_vals)
                            self.env.cr.commit()
                        else:
                            #对于已经存在的asn_line的状态需要进行重新开asn操作,重置asn_line的状态信息
                            if asn_line_buy_sell.state not in ['done','asn_create_success']:
                                asn_line_buy_sell.write({"state":"draft","sap_flag":"N"})
                                self.env.cr.commit()
                            else:
                                #已经开成功的再次重新传送一次
                                asn_line_buy_sell.write({"state":"asn_create_success","sap_flag":"N"})
                                self.env.cr.commit()

                else:
                    #获取asn的条目数据
                    asn_line_vals=asn_line_vals_map.get(asn_key)

                    #获取asn的头部信息
                    asn_vals=asn_vals_map.get(asn_key)
                    line_ids=[]

                    #组装新建数据的asn_vals
                    for raw_asn_line in asn_line_vals:
                        line_ids.append((0,0,raw_asn_line))

                    asn_vals["line_ids"]=line_ids
                    self.env["iac.asn.buy.sell"].create(asn_vals)
                    self.env.cr.commit()
        return True


    @api.model
    def validate_data(self,id_list=None):
        """
        校验数据,补充关键字段
        po校验的必要条件
        1 approve_flag=True 曾经签核通过过
        2 当前po状态不能为 签核中
        3 po_line不能为删除状态
        :return:
        """
        #处理没有补充关键字段的asn vmi
        domain=[('state','in',['draft','validate_fail']),('sap_flag','=','N')]
        last_date=datetime.now()+timedelta(days=-7)
        domain+=[('create_date','>=',odoo.fields.Date.to_string(last_date.date()))]
        if id_list!=None:
            domain+=[('id','in',id_list)]
        buy_sell_asn_list=self.env["iac.asn.buy.sell"].search(domain)

        for buy_sell_asn in buy_sell_asn_list:
            vendor_id = self.env['iac.vendor'].search([('vendor_code','=',buy_sell_asn.vendor_code)],limit=1)
            err_msg_list=[]
            #排除异常信息
            if not vendor_id.exists():
                err_msg="vendor_code dose not exits (%s)" %(buy_sell_asn.vendor_code,)
                err_msg_list.append(err_msg)
                buy_sell_asn.write({
                    "state":"validate_fail",
                    "err_msg":err_msg,
                    })
                continue

            buy_sell_asn.write({
                "plant_id":vendor_id.plant.id,
                "vendor_id":vendor_id.id
                })


            #遍历所有的子条目更新关键字段

            storage_location=""
            domain_2=[('state','in',['draft','validate_fail']),('sap_flag','=','N')]
            domain_2+=[('buy_sell_asn_id','=',buy_sell_asn.id)]
            raw_asn_line_list=self.env["iac.asn.line.buy.sell"].search(domain_2)
            for raw_asn_line in raw_asn_line_list:
                #['draft','validate_fail']),('sap_flag','=','N')
                part_id=self.env["material.master"].search([('part_no','=',raw_asn_line.part_no),('plant_id','=',vendor_id.plant.id)],limit=1)
                line_err_msg_list=[]
                #排除异常信息
                if not part_id.exists():
                    err_msg="part_no dose not exits (%s)" %(raw_asn_line.part_no,)
                    line_err_msg_list.append(err_msg)


                po_id=self.env["iac.purchase.order"].search([('document_erp_id','=',raw_asn_line.po_no)],limit=1)
                #排除异常信息
                if not po_id.exists():
                    err_msg="order code dose not exits (%s)" %(raw_asn_line.po_no,)
                    line_err_msg_list.append(err_msg)
                else:
                    if po_id.approve_flag==False:
                        err_msg="approve_flag is not true"
                        line_err_msg_list.append(err_msg)
                    if po_id.state in ['to_approve']:
                        err_msg="po is not in valid state"
                        line_err_msg_list.append(err_msg)
                po_line_id=self.env["iac.purchase.order.line"].search([('document_erp_id','=',raw_asn_line.po_no),('order_line_code','=',raw_asn_line.po_line_no)],limit=1)

                #排除异常信息
                if not po_line_id.exists():
                    err_msg="order item code dose not exits,PO NO is (%s), PO Line No is ( %s ) " %(raw_asn_line.po_no,raw_asn_line.po_line_no)
                    line_err_msg_list.append(err_msg)
                else:
                    if po_line_id.odoo_deletion_flag==True:
                        err_msg="order item code is deleted,PO NO is (%s), PO Line No is ( %s ) " %(raw_asn_line.po_no,raw_asn_line.po_line_no)
                        line_err_msg_list.append(err_msg)
                    if po_id.plant_id.plant_code=='CP22' and po_line_id.state in ['wait_vendor_confirm','vendor_exception']:
                        err_msg="order item code is not confirmed,PO NO is (%s), PO Line No is ( %s ) " %(raw_asn_line.po_no,raw_asn_line.po_line_no)
                        line_err_msg_list.append(err_msg)

                #异常信息记录之后
                if len(line_err_msg_list)>0:
                    line_vals={
                        "state":"validate_fail",
                        "err_msg":line_err_msg_list,
                        }
                    raw_asn_line.write(line_vals)
                    continue

                #校验没有发生异常的情况下
                line_vals={
                    "state":"validate_success",
                    "vendor_id":vendor_id.id,
                    "plant_id":vendor_id.plant.id,
                    "part_id":part_id.id,
                    "po_id":po_id.id,
                    "po_line_id":po_line_id.id,
                    "storage_location":po_line_id.storage_location,
                    "err_msg":False,
                    }
                storage_location=po_line_id.storage_location
                raw_asn_line.write(line_vals)

            #当明细条目存在异常的情况下
            fail_buy_sell_asn = buy_sell_asn.line_ids.filtered(lambda r: r.state == 'validate_fail' and r.sap_flag=='N')
            if fail_buy_sell_asn.exists():
                buy_sell_asn.write({"state":"validate_fail","storage_location":storage_location})
            else:
                buy_sell_asn.write({"state":"validate_success","err_msg":False,"storage_location":storage_location,"vendor_id":vendor_id.id})
        # ning add 191118 同一颗料数量累加判断可交量是否满足
        for buy_sell_asn in buy_sell_asn_list:
            vendor_asn = buy_sell_asn.vendor_asn
            # 存放唯一的厂商加料号
            header_list = []
            # 存放对应的数量
            qty_list = []
            raw_asn_line_list = self.env["iac.asn.line.buy.sell"].search([('buy_sell_asn_id','=',buy_sell_asn.id)])
            for raw_asn_line in raw_asn_line_list:
                vendor_id = raw_asn_line.vendor_id.id
                part_id = raw_asn_line.part_id.id
                vendor_code = raw_asn_line.vendor_id.vendor_code
                part_no = raw_asn_line.part_id.part_no
                buyer_id = raw_asn_line.part_id.buyer_code_id.id
                qty = raw_asn_line.qty
                plant_id = raw_asn_line.plant_id.id
                part_type = raw_asn_line.part_id.part_type
                header_id = str(vendor_id) + ',' + str(buyer_id) + ',' + str(part_id) + ',' + str(vendor_code) + ',' + str(
                    part_no) + ',' + str(plant_id)
                # CP22和TP02的不判断
                if plant_id != 28 and plant_id != 41 and plant_id != 51:
                    # part_type是ZROH的要卡控可交量
                    if part_type == 'ZROH':
                        if header_id not in header_list:
                            header_list.append(header_id)
                            qty_list.append(qty)
                        else:
                            index = header_list.index(header_id)
                            qty_list[index] = qty + qty_list[index]
            if len(header_list) > 0:
                for i in range(len(header_list)):
                    try:
                        flag, max_qty, max_qty_id = self.env["asn.jitrule"].kakong(int((header_list[i].split(','))[0]),
                                                                                   int((header_list[i].split(','))[1]),
                                                                                   int((header_list[i].split(','))[2]),
                                                                                   (header_list[i].split(','))[3],
                                                                                   (header_list[i].split(','))[4],
                                                                                   int((header_list[i].split(','))[5]))
                        if flag == False:
                            continue
                        else:
                            if qty_list[i] > max_qty:
                                err_msg = u"最大可交量不足,同一颗料数量累加,ASN数量为( %s ),最大可交量为( %s ),vendor_code 是 ( %s );part_no 是 ( %s )" % (
                                qty_list[i], max_qty, (header_list[i].split(','))[3], (header_list[i].split(','))[4])
                                line_vals = {
                                    "state": "validate_fail",
                                    "err_msg": err_msg,
                                }
                                for raw_asn_line in self.env["iac.asn.line.buy.sell"].search(
                                        [('part_no', '=', (header_list[i].split(','))[4]),('vendor_asn','=',vendor_asn)]):
                                    raw_asn_line.write(line_vals)
                                # raise UserError(err_msg)
                    except:
                        l_err_msg = traceback.format_exc()
                        try:
                            error_msg = str(traceback.format_exc()).split('UserError:')[1]
                        except:
                            error_msg = l_err_msg

                        line_vals = {
                            "state": "validate_fail",
                            "err_msg": error_msg,
                        }
                        for raw_asn_line in self.env["iac.asn.line.buy.sell"].search(
                                [('part_no', '=', (header_list[i].split(','))[4]), ('vendor_asn', '=', vendor_asn)]):
                            raw_asn_line.write(line_vals)
        self.env.cr.commit()

    @api.model
    def validate_rule(self,id_list=None):
        """
        进行业务规则校验
        目前只校验 Storage Location
        """
        domain=[('state','in',['rule_fail',"validate_fail",'validate_success']),('sap_flag','=','N')]
        last_date=datetime.now()+timedelta(days=-7)
        domain+=[('create_date','>=',odoo.fields.Date.to_string(last_date.date()))]
        if id_list!=None:
            domain+=[('id','in',id_list)]
        buy_sell_asn_list=self.env["iac.asn.buy.sell"].search(domain)
        for raw_asn in buy_sell_asn_list:

            #校验 storage_location
            storage_locations = []
            for raw_asn_line in raw_asn.line_ids:
                storage_locations += [raw_asn.storage_location]

            #校验storage location 是否唯一
            if len(set(storage_locations)) > 1:
                raw_asn_vals={
                    "state":"rule_fail",
                    "err_msg":"Storage Location is different",
                    }
                raw_asn.write(raw_asn_vals)
                continue

            #更新明细条目状态
            domain_2=[('state','in',['rule_fail','validate_success']),('sap_flag','=','N')]
            domain_2+=[('buy_sell_asn_id','=',raw_asn.id)]
            raw_asn_line_list=self.env["iac.asn.line.buy.sell"].search(domain_2)
            for raw_asn_line in raw_asn_line_list:
                raw_asn_line_vals={
                    "state":"rule_success",
                    "err_msg":False,
                    }
                raw_asn_line.write(raw_asn_line_vals)

            raw_asn_vals={
                    "state":"rule_success",
                    "err_msg":False,
                    }
            raw_asn.write(raw_asn_vals)
        self.env.cr.commit()

    @api.model
    def create_asn(self,id_list=None):
        """
        对业务校验通过的数据进行创建asn操作
        特殊要求针对一个buy_sell 开立asn条目失败的情况下，整个asn会被废弃
        开立失败的asn在1周内尝试重新开立
        :return:
        """
        #业务校验完成的情况下，对业务校验的通过的数据进行创建asn工作
        domain=[('state','in',['rule_success','asn_create_fail']),('sap_flag','=','N')]
        last_date=datetime.now()+timedelta(days=-7)
        domain+=[('create_date','>=',odoo.fields.Date.to_string(last_date.date()))]
        if id_list!=None:
            domain+=[('id','in',id_list)]
        raw_asn_list=self.env["iac.asn.buy.sell"].search(domain)

        #遍历全部需要开asn的数据
        for raw_asn in raw_asn_list:
            asn_vals={
                "buy_sell_asn_id":raw_asn.id,
                "plant_id":raw_asn.plant_id.id,
                "vendor_id":raw_asn.vendor_id.id,
                "customer_country":raw_asn.vendor_id.bank_country.id,
                "customer_currency":raw_asn.vendor_id.currency.id,
                "storage_location":raw_asn.storage_location,
                "create_mode":"auto_create"
                #"buyer_erp_id":raw_asn.vendor_id.user_id.partner_id.buyer_code,
            }

            #buy sell ASN的处理方式不同的是,总是尝试创建ASN 允许部分条目成功创建ASN
            asn_result=self.env["iac.asn"].create(asn_vals)

            #遍历asn_vmi的条目,进行创建数据准备操作
            line_ids = []
            asn_line_list=[]
            domain_2=[('state','in',['rule_success','asn_create_fail']),('sap_flag','=','N')]
            domain_2+=[('buy_sell_asn_id','=',raw_asn.id)]
            raw_asn_line_list=self.env["iac.asn.line.buy.sell"].search(domain_2)
            for raw_asn_line in raw_asn_line_list:
                #plant_id,buyer_id,cancel_qty,vendor_asn,vendor_asn_item,buyer_erp_id,plant_code,po_code,po_line_code,buyer_code,part_no
                line_vals={
                    "vendor_id":raw_asn_line.vendor_id.id,
                    "part_id":raw_asn_line.part_id.id,
                    "po_id":raw_asn_line.po_id.id,
                    "po_line_id":raw_asn_line.po_line_id.id,
                    "asn_qty":raw_asn_line.qty,
                    "storage_location":raw_asn_line.storage_location,
                    "vendor_asn":raw_asn_line.vendor_asn,
                    "vendor_asn_item":raw_asn_line.vendor_asn_item,
                    "buy_sell_asn_id":raw_asn_line.buy_sell_asn_id.id,
                    "buy_sell_asn_line_id":raw_asn_line.id,
                    "asn_no":asn_result.asn_no,
                    "cancel_qty":raw_asn_line.qty,
                    "plant_id":raw_asn_line.plant_id.id,
                    "buyer_id":raw_asn_line.po_id.buyer_id.id,
                    "buyer_erp_id":raw_asn_line.po_id.buyer_id.buyer_erp_id,
                    "buyer_code":raw_asn_line.po_id.buyer_id.buyer_erp_id,
                    "plant_code":raw_asn_line.plant_id.plant_code,
                    "po_code":raw_asn_line.po_no,
                    "po_line_code":raw_asn_line.po_line_no,
                    "part_no":raw_asn_line.part_no,
                }
                asn_line_list.append(line_vals)



            #记录开立asn的异常条目信息,key为 buy_sell_asn_line_id
            buy_sell_fail_vals={}
            #记录开立asn_line 成功的id列表
            asn_line_ids_list=[]



            #条目开立asn失败的情况下,进行数据回滚处理
            for asn_line_vals in asn_line_list:
                #判断po_line的open_qty是否符合条件,符合条件的才会开立asn
                po_line_rec=self.env["iac.purchase.order.line"].browse(asn_line_vals.get("po_line_id"))

                self.env.cr.execute("SELECT                                     " \
                                    "	o_gr_count,o_asn_count,o_open_count      " \
                                    "FROM                                       " \
                                    "	public.proc_po_part_info (              " \
                                    "		%s,                      " \
                                    "		%s,                      " \
                                    "		%s                       " \
                                    "	)                             ",
                                    (po_line_rec.order_id.id, po_line_rec.id,
                                     po_line_rec.part_id.id,))
                gr_count=0
                asn_count=0
                open_count=0
                part_result=self.env.cr.fetchall()

                gr_count=part_result[0][0]
                asn_count=part_result[0][1]
                open_count=part_result[0][2]
                if po_line_rec.exists() and open_count>=asn_line_vals.get("asn_qty"):
                    #开立asn过程可能引发异常,这里捕获异常信息进行记录并重新引发异常返回到顶层except
                    try:
                        asn_line_vals["asn_id"]=asn_result.id
                        asn_line_rec=self.env["iac.asn.line"].create_with_max_qty_check(asn_line_vals)
                        asn_line_rec.buy_sell_asn_line_id.write({"state":"asn_create_success","err_msg":False})
                        #回写asn_id 和asn_line_id
                        asn_line_rec.buy_sell_asn_line_id.write({
                            "asn_id":asn_result.id,
                            "asn_line_id":asn_line_rec.id,
                            })
                        asn_line_ids_list.append(asn_line_rec.id)
                    except:
                        l_err_msg= traceback.format_exc()
                        try:
                            error_msg = str(traceback.format_exc()).split('UserError:')[1]
                        except:
                            error_msg = l_err_msg

                        fail_vals={
                             "err_msg":error_msg,
                            # "err_msg":"asn_qty must less then open_qty",
                            "state":"asn_create_fail"
                        }
                        buy_sell_fail_vals[asn_line_vals["buy_sell_asn_line_id"]]=fail_vals
                        pass

                else:
                    #asn_qty 大于open_qty 记录错误信息后,引发异常信息退出当前循环
                    fail_vals={
                        "err_msg":"asn_qty is greater than open_qty;asn_qty is (%s),open_qty is (%s)" %(asn_line_vals.get("asn_qty"),open_count),
                        "state":"asn_create_fail"
                    }
                    buy_sell_fail_vals[asn_line_vals["buy_sell_asn_line_id"]]=fail_vals
                    #buy_sell_asn_line_rec=self.env["iac.asn.line.buy.sell"].browse(asn_line_vals["buy_sell_asn_line_id"])
                    #buy_sell_asn_line_rec.write({"err_msg":"asn_qty must less then open_qty","state":"asn_create_fail"})
                    #self.env.cr.commit()
                    #buy_sell_asn_line_rec=self.env["iac.asn.line.buy.sell"].browse(asn_line_vals["buy_sell_asn_line_id"])
                    #buy_sell_asn_line_rec.write({"err_msg":"asn_qty must less then open_qty","state":"asn_create_fail"})

            #判断明细条目中是否有开立ASN失败的条目
            #如果当前的Asn没有成功创建的条目，那么则回滚数据,撤销空的asn header
            if len(asn_line_ids_list)==0:
                self.env.cr.rollback()
                raw_asn.write(
                    {
                        "state":"asn_create_fail",
                        }
                )
                self.env.cr.commit()
            else:
                fail_buy_sell_asn = asn_result.buy_sell_asn_id.line_ids.filtered(lambda r: r.state == 'asn_create_fail')
                if not fail_buy_sell_asn.exists():
                    #没有发生异常的情况下记录
                    raw_asn.write(
                        {
                            "state":"asn_create_success",
                            }
                    )
                    self.env.cr.commit()

            #记录开立asn_line失败的日志信息
            for asn_line_buy_sell_id in buy_sell_fail_vals:
                fail_vals=buy_sell_fail_vals[asn_line_buy_sell_id]
                buy_sell_asn_line_rec=self.env["iac.asn.line.buy.sell"].browse(asn_line_buy_sell_id)
                buy_sell_asn_line_rec.write(fail_vals)
            self.env.cr.commit()


    @odoo_env
    @api.model
    def job_iac_asn_buy_sell(self):
        """
        进行数据有效性校验
        对数据有效进行业务规则校验
        对通过业务规则校验的创建asn
        提交数据校验失败的、业务规则校验失败的、创建asn失败的进行提交到sap
        提交创建asn成功的进行提交到sap
        :return:
        """
        #从SAP 系统加载buy sell ASN
        logging.info("job_iac_asn_buy_sell start,thread name is %s" %(threading.currentThread().getName()))
        self.load_buy_sell_asn_data()

        #数据有效性校验
        self.validate_data()
        #业务规则校验
        self.validate_rule()

        #创建asn数据
        self.create_asn()

        #数据处理过程完成之后,进行接口调用,包括调用sap系统失败的和刚创建asn成功的状态
        self.send_buy_sell_asn_to_sap()
        logging.info("job_iac_asn_buy_sell run success,thread name is %s" %(threading.currentThread().getName()))

    @api.model
    def send_buy_sell_asn_to_sap(self,id_list=None):
        #数据处理过程完成之后,进行接口调用,包括调用sap系统失败的和刚创建asn成功的状态
        domain=[('state','in',['rule_fail','validate_fail','asn_create_fail','asn_create_success',]),('sap_flag','=','N')]
        last_date=datetime.now()+timedelta(days=-7)
        if id_list!=None:
            domain+=[('id','in',id_list)]
        raw_asn_list=self.env["iac.asn.buy.sell"].search(domain)
        asn_id_list=[]
        for raw_asn in raw_asn_list:
            try:
                #遍历asn_buy_sell 的条目调用相应的接口
                domain_2=[('state','in',['rule_fail','validate_fail','asn_create_fail','asn_create_success',]),('sap_flag','=','N')]
                domain_2+=[('buy_sell_asn_id','=',raw_asn.id)]
                raw_asn_line_list=self.env["iac.asn.line.buy.sell"].search(domain_2)
                for raw_asn_line in raw_asn_line_list:

                    #调用sap系统告知返回状态
                    rpc_result=raw_asn_line.sap_api_odoo_asn_008()
                    #只要调用过一次就认为已经处理完成
                    raw_asn_line.write({
                        "sap_flag":"Y",
                        })
                    if raw_asn_line.state in ['asn_create_success']:
                        raw_asn_line.write({
                            "state":"done",
                            })
                    self.env.cr.commit()

                    #只有创建ASN成功的项目才调用asn_001,避免重复调用asn_001接口
                    if raw_asn_line.state in ['asn_create_success','done'] and raw_asn_line.asn_id.id not in asn_id_list:
                        rpc_result=raw_asn_line.asn_id.push_to_sap_asn_001()
                        raw_asn_line.write({
                            "state":"done",
                            "sap_flag":"Y",
                            })
                        self.env.cr.commit()
                        asn_id_list.append(raw_asn_line.asn_id.id)
                raw_asn.write({"state":"done","sap_flag":"Y"})
                self.env.cr.commit()
            except:
                traceback.print_exc()
                raw_asn.write({
                    "state":"sap_fail",
                    "sap_flag":"Y",
                    "err_msg":traceback.format_exc()
                    })
                self.env.cr.commit()




class iacAsnLineBuySell(models.Model):
    _name = "iac.asn.line.buy.sell"

    vendor_code = fields.Char("VENDOR_CODE")
    vendor_asn = fields.Char("VENDOR_ASN")
    vendor_asn_item = fields.Char("VENDOR_ASN_ITEM")
    po_no = fields.Char("PO_NO")
    po_line_no = fields.Char("PO_LINE_NO")
    part_no = fields.Char("PART_NO")
    qty = fields.Float("QTY",digits=(18,4))
    state = fields.Selection([('draft','Draft'),
                          ('done','Done'),
                          ('validate_success','Validate Success'),
                          ('validate_fail','Validate Fail'),
                          ('rule_fail','Rule Fail'),
                          ('rule_success','Rule Success'),
                          ('asn_create_fail','Asn Create Fail'),
                          ('asn_create_success','Asn Create Success'),
                          ('sap_fail','Send SAP Fail')
                         ],default='draft',string='status')
    note = fields.Text('Text')

    asn_id = fields.Many2one('iac.asn',string='ASN')
    asn_line_id = fields.Many2one('iac.asn.line',string='ASN Line Info')
    buy_sell_asn_id = fields.Many2one('iac.asn.buy.sell',string='Buy Sell ASN Info')
    plant_id = fields.Many2one('pur.org.data',string='Plant Info')
    vendor_id = fields.Many2one('iac.vendor',string='Vendor Info')
    po_id = fields.Many2one('iac.purchase.order',string='PO Info')
    po_line_id = fields.Many2one('iac.purchase.order.line',string='PO Line Info')
    part_id = fields.Many2one('material.master',string='Material Info')

    err_msg = fields.Text('Error Message')
    sap_flag=fields.Selection([('Y','YES'),('N','NO')],string="Send To SAP Flag",default="N")
    storage_location = fields.Char('Storage Location')
    ep_status = fields.Char(string="EP Status", compute='_taken_ep_status')

    @api.one
    def _taken_ep_status(self):
        """
        获取asn_line 状态
        :return:
        """
        if self.state in ['asn_create_success','sap_fail','done']:
            self.ep_status='0'
            return
        elif self.state in ['validate_fail','rule_fail','asn_create_fail']:
            self.ep_status='1'
            return
        else:
            self.ep_status='2'
            return


    def sap_api_odoo_asn_008(self):
        sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
        data = {
            "id": self.id,
            "biz_object_id": self.id,
            "odoo_key":sequence,
        }
        rpc_result, rpc_json_data, log_line_id, exception_log = self.env[
            'iac.interface.rpc'].invoke_web_call_with_log('ODOO_ASN_008', data)
        if not rpc_result:
            return False
        return True