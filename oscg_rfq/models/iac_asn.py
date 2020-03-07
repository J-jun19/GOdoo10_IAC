# -*- coding: utf-8 -*-
import pytz
import time
import odoo
from datetime import datetime
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import pdb
from functools import wraps
import  traceback
import threading


class iacASN(models.Model):

    _inherit='iac.asn'

    @api.model
    def get_vendor_asn(self,vendor_id,storage_location):
        """
        获取指定vendor的当天的asn号码,根据数据库中的数据情况动态产生
        vendor_code 后6位+ 楼栋 +年月日(YYMMDD)+当天的流水号(001~999)
        :param vendor_id:
        :return:
        """
        vendor_rec=self.env["iac.vendor"].browse(vendor_id)
        vendor_code_6=vendor_rec.vendor_code[-6:]
        #获取ASN号码前缀
        asn_code_param='asn_code_' + (vendor_rec.plant.plant_code or '') + '_'+ (storage_location or '')
        asn_code_prefix = self.env['ir.config_parameter'].get_param(asn_code_param,default='A')
        start_time=datetime.today()

        dt = datetime.now()
        start_time=dt.strftime('%Y-%m-%d')+" 00:00:00"
        end_time=dt.strftime('%Y-%m-%d')+" 23:59:59"
        self.env.cr.execute("SELECT                                             " \
                            "	%s || to_char(now(), 'YYMMDD') || lpad(  " \
                            "		CAST (COUNT(*)+1 AS VARCHAR),                 " \
                            "		3,                                          " \
                            "		'0'                                         " \
                            "	) asn_no                                        " \
                            "FROM                                               " \
                            "	public.iac_asn T                              " \
                            "WHERE                                              " \
                            "	T .vendor_id = %s                             " \
                            "AND T .create_date >= to_timestamp(                " \
                            "	%s,                          " \
                            "	'YYYY-MM-DD HH24:MI:SS'                         " \
                            ")                                                  " \
                            "AND T .create_date <= to_timestamp(                " \
                            "	%s,                          " \
                            "	'YYYY-MM-DD HH24:MI:SS'                         " \
                            ")                                                  "
        ,(asn_code_prefix,vendor_id,start_time,end_time))
        result=self.env.cr.fetchall()
        asn_no=vendor_code_6+result[0][0]
        return asn_no

    @api.model
    def create(self, vals):
        '''ASN code的编码规则：vendor code + A(B) + yyyyMMdd + nnn; config_parameter: asn.code_plantcode_storagelocation'''
        vendor=self.env["iac.vendor"].browse(vals.get('vendor_id'))
        if not vendor.exists():
            raise UserError(_('RFQ Vendor Info Not Exists!'))

        if not vendor.vendor_code:
            raise UserError(_('RFQ vendor_id has not vendor_code!'))

        #asn_code = self.env['ir.config_parameter'].get_param('asn.code_' + (vendor.plant.plant_code or '') + '_'+ (vals.get('storage_location','') or ''))
        #asn_no= vendor.vendor_code[-6:] + (asn_code or 'A') + self.env['ir.sequence'].next_by_code('iac.asn')

        asn_no=self.get_vendor_asn(vals.get('vendor_id'),vals.get('storage_location','') )
        vals["asn_no"]=asn_no
        r = super(iacASN, self).create(vals)
        return r



    @api.multi
    def push_to_sap_asn_001(self):
        for asn_id in self.ids:
            #排除已经与SAP系统同步成功的情况
            asn_rec=self.env["iac.asn"].browse(asn_id)
            if not asn_rec.state in ['draft','sap_fail']:
                continue
            elif asn_rec.state=='sap_fail':
                for asn_lines in asn_rec.line_ids:
                    if asn_lines.asn_qty != asn_lines.cancel_qty:
                        raise UserError(u'当前ASN是cancel失败的asn,无法在此按钮送SAP,请回到MM Cancel or Vendor Cancel菜单中送SAP！')
            sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
            vals = {
                "id": asn_id,
                "biz_object_id": asn_id,
                "odoo_key":sequence,
            }
            try:
                rpc_result, rpc_json_data, log_line_id, exception_log = self.env['iac.interface.rpc'].invoke_web_call_with_log(
                    'ODOO_ASN_001', vals)
                if rpc_result:
                    asn_rec.write({'state':'sap_ok','sap_flag':True})
                else:
                    asn_rec.write({'state':'sap_fail','rpc_note': rpc_json_data})
                #r.message_post(body=u'•SAP API ODOO_ASN_001: %s'%rpc_json_data['Message']['Message'])
            except:
                traceback.print_exc()
                continue
        return True

    @api.multi
    def push_to_sap_asn_002(self):
        """
        当变更ASN数量的时候需要调用这个接口同步数据到SAP系统
        :return:
        """
        for asn_id in self.ids:
            #排除已经与SAP系统同步成功的情况
            #if not (r.state  in ['draft','sap_fail']):
            #    continue
            sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
            vals = {
                "id": asn_id,
                "biz_object_id": asn_id,
                "odoo_key":sequence
                }

            rpc_result, rpc_json_data, log_line_id, exception_log = self.env['iac.interface.rpc'].invoke_web_call_with_log(
                'ODOO_ASN_002', vals)
            asn_rec=self.env["iac.asn"].browse(asn_id)
            if rpc_result:
                asn_rec.write({'state':'sap_ok'})
                self.env.cr.commit()
            else:
                asn_rec.write({'state':'sap_fail','rpc_note': rpc_json_data})
                self.env.cr.commit()
                #r.message_post(body=u'•SAP API ODOO_ASN_001: %s'%rpc_json_data['Message']['Message'])

        return True

    @api.multi
    def push_to_sap_asn_004(self):
        """
        当变更ASN表头的时候,需要调用这个接口同步数据到SAP
        无限循环bug出现,for in self 循环调用sap接口会出现
        :return:
        """
        asn_id_list=[]
        for asn_id in self.ids:
            asn_id_list.append(asn_id)
        for asn_id in asn_id_list:
            asn_rec=self.env["iac.asn"].browse(asn_id)
            #排除已经与SAP系统同步成功的情况
            if not asn_rec.state in ['draft','sap_fail','sap_ok']:
                continue
            sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
            vals = {
                "id": asn_rec.id,
                "biz_object_id": asn_rec.id,
                "odoo_key":sequence
                }
            rpc_result, rpc_json_data, log_line_id, exception_log = self.env['iac.interface.rpc'].invoke_web_call_with_log(
                'ODOO_ASN_004', vals)
            if rpc_result:
                asn_rec.write({'state':'sap_ok'})
            else:
                asn_rec.write({'state':'sap_fail','rpc_note': rpc_json_data})
                #r.message_post(body=u'•SAP API ODOO_ASN_001: %s'%rpc_json_data['Message']['Message'])

        return True

    def send_to_sap(self):
        """
        提供action 菜单对需要同步的数据进行同步
        :return:
        """
        #批量调用接口同步数据到SAP系统
        for asn_id in self.ids:
            asn_rec=self.env["iac.asn"].browse(asn_id)
            if asn_rec.state not in ['sap_fail']:
                raise UserError('Asn No is %s not in sap_fail state,can not send to SAP' %(asn_rec.asn_no,))

        for asn_id in self.ids:
            asn_rec=self.env["iac.asn"].browse(asn_id)
            asn_rec.push_to_sap_asn_001()

    @api.model
    def asn_vmi(self):
        vmi = self.env['iac.asn.vmi.sap']
        vmi.job_sap_rpc_get_vmi_data()
        return vmi.job_create_asn_vmi()


    @api.model
    def asn_buy_sell(self):
        '''发起api调用,根据返回数据生成asn,主要校验po／max数量，可以部分创建成功，调用sap接口返回创建结果。'''
        self.env['iac.asn.buy.sell.sap'].job_sap_rpc_get_buy_sell_data()
        return self.env['iac.asn.buy.sell.sap'].job_create_asn_buy_sell()

    @api.model
    def job_clean_asn_from_sap(self):
        '''
        主動調用 SAP 接口獲取過期 ASN 資料后, 一筆一筆Call ASN修改的 SAP 接口, SAP 返回成功 Odoo 清除 ASN .
        '''
        rpc_result, rpc_json_data = self.env['iac.asn'].sap_rpc_get('ODOO_ASN_003')
        if rpc_result:
            asn = self.env['iac.asn'].search([('asn_id.name','=',rpc_json_data.get('Document').get('ASN_NO'))])
            if not asn:
                return False,['asn_id is not exist!']
            vals = rpc_json_data.get('Document').get('ITEM')
            for val in vals:
                al = self.env['iac.asn.line'].search([('asn_id.name','=',val.get('ASN_NO')),('asn_line_no','=',val.get('ASN_ITEM'))])
                if al:
                    al.write({'REDUCE_QTY': float(val.get('REDUCE_QTY'))})
            # change for sap
            data = {
                "id": asn.id,
                "biz_object_id": asn.id
            }
            rpc2, data2, log_line_id, exception_log = self.env[
                'iac.interface.rpc'].invoke_web_call_with_log('ODOO_ASN_002', data)

            if rpc2:
                for l in asn.line_ids:
                    l.write({'asn_qty': l.REDUCE_QTY})
                    asnmax = self.env['asn.maxqty'].get_maxr(l.asn_id.vendor_id.id,l.part_id.id)
                    if asnmax:
                        asnmax.shipped = asnmax.shipped - l.REDUCE_QTY
            asn.message_post(body=u'•SAP API ODOO_ASN_002: %s'%data2['Message']['Message'])

        return True

    @api.model
    def sap_rpc_get(self,method):
        sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
        vals = {
            "id": int(sequence),
            "biz_object_id": int(sequence),
        }
        rpc_result, rpc_json_data, log_line_id, exception_log = self.env['iac.interface.rpc'].invoke_web_call_with_log(
            method, vals)
        return rpc_result, rpc_json_data


class iacASNLine(models.Model):
    _inherit = 'iac.asn.line'

    @api.model
    def create_with_max_qty_check(self, vals):
        """
        判断卡控规则和最大可交量,如果需要卡控并且不满足最大可交量的情况下,引发异常
        新开的PO必须是更新SAP成功的，才能开ASN
        change过程中的PO不能开ASN
        正常操作创建相应的ASN Line 信息
        :param vals:
        :return:
        """
        po_rec=self.env["iac.purchase.order.asn"].browse(vals.get("po_id"))
        if not po_rec.exists():
            raise UserError("PO Information is not correct ")
        #除CP22南京厂之外都不卡开PO的状态
        if (po_rec.state not in ['wait_vendor_confirm','vendor_confirmed','vendor_exception']) and \
            (po_rec.vendor_id.plant.plant_code not in ['CP22']):
            raise UserError("PO state is not in [ 'wait_vendor_confirm','vendor_confirmed','vendor_exception'] can not create ASN")
        if po_rec.vendor_id.plant.plant_code=='CP22' and po_rec.state not in ['vendor_confirmed']:
            raise UserError("Plant Code is CP22 and PO state is not in ['vendor_confirmed'] can not create ASN")

        po_line_rec=self.env["iac.purchase.order.line"].browse(vals.get("po_line_id"))
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
        #校验po_line中的quantity是否大于入料数量
        if po_line_rec.quantity-gr_count<=0:
            raise UserError("PO Code is %s ,PO Line Code is %s ,PO Line quantity is %s ,GR quantity is %s"%
                            (po_rec.document_erp_id,po_line_rec.order_line_code,po_line_rec.quantity,gr_count))

        part_rec=self.env["material.master.po.line"].browse(vals["part_id"])
        part_no=part_rec.part_no
        buyer_code=part_rec.buyer_code_id.id
        vendor_rec=self.env["iac.vendor"].browse(vals["vendor_id"])
        vendor_code=vendor_rec.vendor_code
        plant_id = vendor_rec.plant.id

        #南京厂CP22 不考虑最大可交量
        if po_rec.plant_id.plant_code=="CP22" or po_rec.plant_id.plant_code=="TP02" or po_rec.plant_id.plant_code=="CP29":
            rec = super(iacASNLine, self).create(vals)
            super(iacASNLine,rec).write({"source_code":rec.part_id.sourcer})
            if not rec.buyer_id.exists():
                super(iacASNLine,rec).write({"buyer_id":po_rec.buyer_id.id})
            rec.asn_line_no = len(rec.asn_id.line_ids.filtered(lambda x: x.id != rec.id)) + 1
            return rec

        #获取卡控规则和最大可交量信息,这里可能会出现异常
        flag,max_qty,max_qty_id=self.env["asn.jitrule"].kakong(vals["vendor_id"],buyer_code,vals["part_id"],vendor_code,part_no,plant_id)

        #不需要卡控规则的情况下,白名单存在的情况下,直接创建ASN Line
        if flag==False:
            rec = super(iacASNLine, self).create(vals)
            super(iacASNLine,rec).write({"source_code":rec.part_id.sourcer})
            if not rec.buyer_id.exists():
                super(iacASNLine,rec).write({"buyer_id":po_rec.buyer_id.id})
            rec.asn_line_no = len(rec.asn_id.line_ids.filtered(lambda x: x.id != rec.id)) + 1
            return rec

        #需要卡控规则的情况下,比较最大可交量是否满足
        if vals["asn_qty"]<=max_qty:
            #最大可交量可以满足
            if vals["asn_qty"]<=0:
                raise UserError("ASN Line quantity must greater than zero")
            rec = super(iacASNLine, self).create(vals)
            super(iacASNLine,rec).write({"source_code":rec.part_id.sourcer})
            if not rec.buyer_id.exists():
                super(iacASNLine,rec).write({"buyer_id":po_rec.buyer_id.id})
            rec.asn_line_no = len(rec.asn_id.line_ids.filtered(lambda x: x.id != rec.id)) + 1

            #增加ASN数量，减少最大可交量
            asn_max_rec=self.env["asn.maxqty"].browse(max_qty_id)
            asn_max_rec.minus_max_qty(vals["asn_qty"])
            return rec
        else:
            #不满足最大可交量
            err_msg=u"最大可交量不足,ASN数量为( %s ),最大可交量为( %s )" % (vals["asn_qty"],max_qty,)
            raise UserError(err_msg)

    @api.multi
    def write(self,vals):
        """
        不检查最大可交量的情况下,必须更新最大可交量
        :param vals:
        :return:
        """
        #变更最大可交量的情况下，要对比是否减小最大可交量
        if "asn_qty" in vals:
            if self.asn_qty<vals["asn_qty"]:
                err_msg=u"ASN单号为( %s ),ASN Line NO 为( %s ), 修改的ASN数量不能大于已经开立的ASN数量" % (self.asn_no,self.asn_line_no)
                raise UserError(err_msg)
            minus_qty=self.asn_qty-vals["asn_qty"]
            result=super(iacASNLine,self).write(vals)
            max = self.env['asn.maxqty'].search([('vendor_id', '=', self.vendor_id.id), ('part_id', '=', self.part_id.id),('state','=','done')],limit=1)
            if max.exists():
                #最大可交量存在的情况下,更新最大可交量,值允许增大最大可交量
                max.add_max_qty(minus_qty)
            else:
                res = self.env['asn.maxqty'].search([('plant_id', '=', self.plant_id.id),
                                                     ('vendor_id', '=', self.vendor_id.id),
                                                     ('part_id', '=', self.part_id.id),
                                                     ('state', '=', 'cancel')], order='id desc', limit=1)
                if res:
                    engineid = res.engineid
                else:
                    engineid = 'IACD'

                self._cr.execute(
                    'insert into asn_maxqty(version,vendorcode,vendor_id,part_id,plant_id,shipped_qty,maxqty,engineid,state,plant,'
                    'material,division,division_id,create_date,write_date,create_uid,write_uid)'
                    'values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    ('version', self.vendor_id.vendor_code, self.vendor_id.id, self.part_id.id,
                     self.plant_id.id, 0, 0, engineid, 'done', self.plant_id.plant_code,
                     self.part_id.part_no,
                     self.part_id.division_id.division, self.part_id.division_id.id,
                     datetime.now(), datetime.now(),
                     self._uid, self._uid))
                self.env.cr.commit()

                r = self.env['asn.maxqty'].search([('plant_id', '=', self.plant_id.id),
                                                   ('part_id', '=', self.part_id.id),
                                                   ('vendor_id', '=', self.vendor_id.id),
                                                   ('state', '=', 'done')])
                r.add_max_qty(minus_qty)

        else:
            result=super(iacASNLine,self).write(vals)

        return result

    @api.one
    def apply_with_cancel_qty(self):
        """
        只能用asn_line 对象调用
        应用cancel_qty来增大最大可交量
        :param vals:
        :return:
        """
        qty_change=self.asn_qty-self.cancel_qty
        vendor_id=self.asn_id.vendor_id.id
        part_id=self.part_id.id
        vendor_code=self.asn_id.vendor_id.vendor_code
        part_no=self.part_id.part_no
        plant_id = self.asn_id.plant_id.id
        plant_code = self.asn_id.plant_id.plant_code
        buyer_id = self.part_id.buyer_code_id.id
        asn_no = self.asn_no
        asn_line_no = self.asn_line_no
        asn_line_id = self.id

        #增大最大可交量
        if qty_change>0.000001:
            try:
                flag, max_qty, max_qty_id = self.env["asn.jitrule"].kakong(vendor_id, buyer_id,part_id, vendor_code, part_no,plant_id)
            except:
                flag = True
            if flag == True:

                #ning update 190402 cancel数量累加到可用可交量上
                result = self.env['asn.maxqty'].search([('plant_id', '=', plant_id),
                                                        ('part_id', '=', part_id),
                                                        ('vendor_id', '=', vendor_id),
                                                        ('state', '=', 'done')])
                if result:
                    vals = {
                        'increase_qty': qty_change,
                        'comments': 'ASN'+ str(asn_no) +'第'+ str(asn_line_no) +'行cancel产生的可交量',
                        'asn_max_qty_id': result.id,
                        'asn_line_id':asn_line_id
                    }
                    self.env['iac.asn.max.qty.create.line.update'].create(vals)
                    self.env.cr.commit()
                    # result.write({'shipped_qty':result.shipped_qty-qty_change})
                else:
                    div = self.env['material.master.asn'].browse(part_id)
                    res = self.env['asn.maxqty'].search([('plant_id', '=', plant_id),
                                                         ('vendor_id', '=', vendor_id),
                                                         ('part_id', '=', part_id),
                                                         ('state', '=', 'cancel')], order='id desc', limit=1)
                    if res:
                        engineid = res.engineid
                    else:
                        engineid = 'IACD'

                    self._cr.execute(
                        'insert into asn_maxqty(version,vendorcode,vendor_id,part_id,plant_id,shipped_qty,maxqty,engineid,state,plant,'
                        'material,division,division_id,create_date,write_date,create_uid,write_uid)'
                        'values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        ('version', vendor_code, vendor_id, part_id,
                         plant_id, 0, 0, engineid, 'done', plant_code,
                         part_no,
                         div.division_id.division, div.division_id.id,
                         datetime.now(), datetime.now(),
                         self._uid, self._uid))
                    self.env.cr.commit()

                    r = self.env['asn.maxqty'].search([('plant_id', '=', plant_id),
                                                       ('part_id', '=', part_id),
                                                       ('vendor_id', '=', vendor_id),
                                                       ('state', '=', 'done')])
                    vals = {
                        'increase_qty': qty_change,
                        'comments': 'ASN'+ str(asn_no) +'第'+ str(asn_line_no) +'行cancel产生的可交量',
                        'asn_max_qty_id': r.id,
                        'asn_line_id': asn_line_id
                    }
                    self.env['iac.asn.max.qty.create.line.update'].create(vals)
                    self.env.cr.commit()
                    # r.write({'shipped_qty': r.shipped_qty - qty_change})

                # self.env["asn.maxqty"].asn_cancel_raise_max_qty(vendor_id,part_id,vendor_code,part_no,qty_change)
        self.write({"asn_qty":self.cancel_qty})

    @api.one
    def write_with_cancel_qty_check(self,vals):
        """
        只能由asn_line 对象调用
        减小cancel_qty 时，需要检查入料数量
        检查通过的情况下，保存数据
        :param vals:
        :return:
        """
        #存在修改数量的情况下,需要改变最大可交量,可能抛出异常
        if "cancel_qty" in vals:
            if self.asn_qty==vals["cancel_qty"]:
                result=super(iacASNLine,self).write(vals)
                return result
            if vals["cancel_qty"]>self.asn_qty:
                raise UserError("Can not raise ASN quantity")

            #校验新录入的ASN数量是否合法,不能小于入料数量
            if self.gr_qty>vals["cancel_qty"]:
                err_msg=u"ASN单号为( %s ),ASN Line NO 为( %s ), ASN数量不能小于已经入料的数量,ASN数量为( %s ),已经入料的数量为( %s )" % \
                        (self.asn_no,self.asn_line_no,vals["cancel_qty"],self.gr_qty)
                raise UserError(err_msg)

            #业务校验通过的情况下,保存数据调用接口
            result=super(iacASNLine, self).write(vals)
            ####
            minus_qty = self.asn_qty - vals["cancel_qty"]
            max = self.env['asn.maxqty'].search(
                [('vendor_id', '=', self.vendor_id.id), ('part_id', '=', self.part_id.id),('state','=','done')], limit=1)
            if max.exists():
                # 最大可交量存在的情况下,更新最大可交量,值允许增大最大可交量
                max.add_max_qty(minus_qty)
            else:
                res = self.env['asn.maxqty'].search([('plant_id', '=', self.plant_id.id),
                                                     ('vendor_id', '=', self.vendor_id.id),
                                                     ('part_id', '=', self.part_id.id),
                                                     ('state', '=', 'cancel')], order='id desc', limit=1)
                if res:
                    engineid = res.engineid
                else:
                    engineid = 'IACD'

                self._cr.execute(
                    'insert into asn_maxqty(version,vendorcode,vendor_id,part_id,plant_id,shipped_qty,maxqty,engineid,state,plant,'
                    'material,division,division_id,create_date,write_date,create_uid,write_uid)'
                    'values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    ('version', self.vendor_id.vendor_code, self.vendor_id.id, self.part_id.id,
                     self.plant_id.id, 0, 0, engineid, 'done', self.plant_id.plant_code,
                     self.part_id.part_no,
                     self.part_id.division_id.division, self.part_id.division_id.id,
                     datetime.now(), datetime.now(),
                     self._uid, self._uid))
                self.env.cr.commit()

                r = self.env['asn.maxqty'].search([('plant_id', '=', self.plant_id.id),
                                                   ('part_id', '=', self.part_id.id),
                                                   ('vendor_id', '=', self.vendor_id.id),
                                                   ('state', '=', 'done')])
                r.add_max_qty(minus_qty)
            #####
            return result
        else:
            result=super(iacASNLine, self).write(vals)
            return result




class iacASNWizard(models.TransientModel):
    _name = "iac.asn.wizard"
    _description = u"asn create wizard"

    vendor_id = fields.Many2one('iac.vendor','Vendor')
    po_lst = fields.Text('PO No. list')
    part_lst = fields.Text('Part No. list')
    date_from = fields.Date('Date from')
    date_to = fields.Date('Date to')

    @api.multi
    def action_confirm(self):
        domain = [('state','in',['vendor_confirmed']),('vendor_id','=',self.vendor_id.id)]
        domain+=[('odoo_deletion_flag','=',False)]
        if self.po_lst:
            po_lst = self.po_lst.split('\n')
            domain += [('order_id.name','in',po_lst)]
        if self.part_lst:
            po_list = self.part_lst.split('\n')
            new_po_list=[]
            for item in po_list:
                new_po_list.append(item.strip())
            domain += [('part_no','in',new_po_list)]
        if self.date_from:
            domain += [('order_date','>',self.date_from)]
        if self.date_to:
            domain += [('order_date','>',self.date_to)]
        lines = self.env['iac.purchase.order.line'].search(domain)
        action = {
            'name': 'PO Line',
            'type': 'ir.actions.act_window',
            'res_model': 'iac.purchase.order.line',
            'view_mode': 'tree',
            'view_type': 'form',
            'view_id':  self.env.ref('oscg_rfq.view_po_line_list').id,
            'search_view_id': self.env.ref("oscg_rfq.view_po_line_search").id,
            'domain': [('id','in',lines.ids)]
        }
        return action

