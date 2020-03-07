# -*- coding: utf-8 -*-

import json
import xlwt
import time,base64
import datetime
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from xlrd import open_workbook
from odoo import models, fields, api
import psycopg2
import logging
from dateutil.relativedelta import relativedelta
from StringIO import StringIO
import pdb
import math
import traceback
import utility



_logger = logging.getLogger(__name__)

def is_float_valid(str_val):
    """
    返回2个值
    对出现科学计数法的字符串转换为标准字符串
    1   处理是否成功
    2   转换成的数值
    :param str_val:
    :return:
    """
    try:
        float_val=float(str_val)
        #获取允许范围之外的小数部分
        input_price=float_val

        #扩大10 的6次方倍
        try_price=input_price*math.pow(10,6)

        #减去整数部分获得小数部分
        digits_part=abs(round(try_price-round(try_price),2))
        price_unit=0
        #如果小数部分大于0.0001 那么表示超过6位，反之小于6位
        if (digits_part>0.0001):
            #1000的不满足,尝试10000
            return False,"%f"%(float_val,)
        else:
            return  True,"%f"%(float_val,)
    except:
        traceback.print_exc()
        pass
    return False,0

class IacRfqQuote(models.Model):
    """rfq quote 只显示 draft sent replay 状态的数据
    """
    _name = 'iac.rfq.quote'
    _inherit = 'iac.rfq'
    _table='iac_rfq'
    _order='id desc'

class IacRfqQuoteAs(models.Model):
    """rfq的可以操作的数据状态为 draf replay
    """
    _name = 'iac.rfq.quote.as'
    _inherit = 'iac.rfq'
    _table='iac_rfq'
    _order='id desc'

    @api.multi
    def button_search_other_price(self):
        """
        查看此笔RFQ之前上传的所有有效记录
        :return:
        """
        action = self.env.ref("oscg_rfq.action_iac_rfq_quote_other_price_form")
        action_window = {
            'name': action.name,
            # 'help': action.help,
            'type': action.type,
            'view_type': "form",
            'view_mode': "form",
            'target': 'current',
            'view_id': self.env.ref('oscg_rfq.view_iac_rfq_quote_other_price_form').id,
            'res_id': self.id,
            'res_model': action.res_model,
        }
        return action_window

    @api.multi
    def action_quotation_send(self):
        if self.filtered(lambda x:x.state not in ['draft']):
            raise UserError(_('State must be draft!'))
        vendor_id_list = []
        rfq_id_list = []
        for rfq_line in self:
            val = {}
            # print rfq_line.id
            val['rfq_id'] = rfq_line.id
            val['create_by'] = self._uid
            val['create_timestamp'] = datetime.datetime.now()
            val['action_type'] = 'AS sent to vendor'
            self.env['iac.rfq.quote.history'].create(val)
            rfq_id_list.append(rfq_line.id)
            if rfq_line.vendor_id.id not in vendor_id_list:
                vendor_id_list.append(rfq_line.vendor_id.id)
        # print self._uid
        as_mail = self.env['res.users'].browse([(self._uid)]).partner_id.email
        as_name = self.env['res.users'].browse([(self._uid)]).partner_id.name
        for item in range(len(vendor_id_list)):
            # print vendor_id_list[item]
            rfq_body_list = []
            body_list = []
            sales_email = self.env['iac.vendor'].browse([(vendor_id_list[item])]).vendor_reg_id.sales_email
            other_emails = self.env['iac.vendor'].browse([(vendor_id_list[item])]).vendor_reg_id.other_emails
            if other_emails:
                email = sales_email+';'+other_emails+';'+as_mail
            else:
                email = sales_email+';'+as_mail
            rfq = self.env['iac.rfq'].search([('id','in',rfq_id_list),('vendor_id','=',vendor_id_list[item])])
            for item in rfq:
                body_list = [item.vendor_id.vendor_code,item.part_id.part_no,item.buyer_code.buyer_name,as_name,
                             item.currency_id.name,str(item.rfq_price),str(item.price_unit),item.valid_from,item.valid_to]
                rfq_body_list.append(body_list)
            # print rfq_line.vendor_id.id
            self.env['iac.email.pool'].button_to_mail('iac-ep_support@iac.com.tw', email,'Wang.Ningg@iac.com.tw'+';'+'Zhang.Pei-Wu@iac.com.tw', '(系統通知) Quote For need Confirm',
                                                      ['Vendor code','Material','Buyer name','AS name','Currency','Price','Price Unit','Valid from','Valid to'], rfq_body_list, 'Vendor')
            # mail_task_vals={
            #     "object_id":rfq_line.id,
            #     "template_id":"oscg_rfq.iac_rfq_quote_as_email"
            # }
            # self.env["iac.mail.task"].add_mail_task(**mail_task_vals)
        #for rfq_line in self:
        #    try:
        #        template = self.env.ref("oscg_rfq.iac_rfq_quote_as_email")
        #        template.send_mail(rfq_line.id, force_send=True)
        #    except:
        #        traceback.print_exc()
        self.write({'state':'sent'})


    @api.multi
    def action_replay_as_confirm(self):
        if self.filtered(lambda x:x.state != 'replay'):
            raise UserError(_('State must be replay'))
        for item in self:
            # 调用utility里公用方法校验涨价原因是否合法
            utility.validate_costup_reason(self,item,'replay')

            val = {}
            val['rfq_id'] = item.id
            val['create_by'] = self._uid
            val['create_timestamp'] = datetime.datetime.now()
            val['action_type'] = 'AS create RFQ'
            self.env['iac.rfq.quote.history'].create(val)
        self.write({'state': 'rfq','type':'rfq'})

        # action = self.env.ref('oscg_rfq.action_iac_rfq_quote_as')
        # action_window = {
        #     'name': action.name,
        #     'help': action.help,
        #     'type': action.type,
        #     'view_type': action.view_type,
        #     'view_mode': "tree",
        #     # 'target': action.target,
        #     'target': 'current',
        #     'res_model': action.res_model,
        #     'auto_refresh':1,
        #     'domain': action.domain,
        #     'view_id': self.env.ref('oscg_rfq.view_iac_rfq_quote_as_list').id,
        # }
        # return action_window

    @api.multi
    def action_cancel(self):
        if self.filtered(lambda x:x.state not in ['draft','replay']):
            raise UserError(_('State must be draft or replay!'))
        for item in self:
            if item.state == 'draft':
                val = {}
                # print rfq_line.id
                val['rfq_id'] = item.id
                val['create_by'] = self._uid
                val['create_timestamp'] = datetime.datetime.now()
                val['action_type'] = 'AS set no action required'
                self.env['iac.rfq.quote.history'].create(val)
            if item.state == 'replay':
                val = {}
                # print rfq_line.id
                val['rfq_id'] = item.id
                val['create_by'] = self._uid
                val['create_timestamp'] = datetime.datetime.now()
                val['action_type'] = 'AS set no action required after vendor confirm'
                self.env['iac.rfq.quote.history'].create(val)
        self.write({'state': 'cancel','active': False})


class IacRfqImportQuote(models.Model):
    """rfq的上传数据,首先上传到当前模型，验证无误的情况下，到正式模型中创建
    """
    _name = 'iac.rfq.import.quote'
    _inherit = 'iac.rfq.import'
    _table='iac_rfq_import'
    _order='as_file_id desc,id asc'

    #lt	moq	mpq	rw	cw	tax

    @api.one
    @api.constrains('lt','moq','mpq','rw','cw','tax')
    def _uniq_check_import_quote(self):
        #if self.lt<=0:
        #    raise UserError('Lt must greater than zero!')
#
        #if self.moq<=0:
        #    raise UserError('moq must greater than zero!')
#
        #if self.mpq<=0:
        #    raise UserError('mpq must greater than zero!')
#
        #if self.rw==False:
        #    raise UserError('rw can not be null!')
#
        #if self.cw<=0:
        #    raise UserError('cw can not be null!')

        if self.tax==False:
            raise UserError('tax can not be null!')

    @api.one
    def apply_quote_import(self):
        """
        导入当前记录的数据到iac_rfq正式表中
        :return:
        """
        #校验有效日期
        if self.valid_from>self.valid_to:
            raise UserError('valid_from can not greater then valid_to')


        #校验数据存在未完工的情况
        domain=[('state','in',['draft','sent','replay'])]
        domain+=[('type','=','quote')]
        domain+=[('vendor_id','=',self.vendor_id.id)]
        domain+=[('part_id','=',self.part_id.id)]
        quote_rec=self.env["iac.rfq"].search(domain,order='id desc',limit=1)

        if quote_rec.exists():
            raise UserError('A quote  with same vendor and part already exists,name is: %s'%quote_rec.name)
        fields = ['part_code','input_price','valid_from','valid_to','price_control','note','vendor_part_no']
        fields = fields+['moq','mpq','lt','cw','rw','tax']
        vals_list=self.read(fields)

        for vals in vals_list:
            val = {}
            vals["plant_id"]=self.plant_id.id
            vals["vendor_id"]=self.vendor_id.id
            vals["currency_id"]=self.currency_id.id
            vals["buyer_code"]=self.part_id.buyer_code_id.id
            vals["part_id"]=self.part_id.id
            vals["division_id"]=self.part_id.division_id.id
            vals["source_code"]=self.part_id.sourcer
            vals["type"]="quote"
            vals["new_type"]="quote_create"
            rfq_obj = self.env["iac.rfq"].create(vals)
            # 调用utility里公用方法产生新旧rfq对照资料
            utility.create_rfq_new_vs_old(self,rfq_obj,'current_rfq_id',rfq_obj.costup_reason_id)

            val['rfq_id'] = rfq_obj.id
            val['create_by'] = self._uid
            val['create_timestamp'] = datetime.datetime.now()
            val['action_type'] = 'CM import'
            self.env['iac.rfq.quote.history'].create(val)

class IacRfqQuoteHistory(models.Model):
    # rfq操作的历史记录表  ning add 18/10/18
    _name = 'iac.rfq.quote.history'

    rfq_id = fields.Many2one('iac.rfq')
    create_by = fields.Many2one('res.users')
    create_timestamp = fields.Datetime()
    action_type = fields.Char()


class IacRfqQuoteVendor(models.Model):
    """rfq的可以操作的数据状态为 draf replay
    """
    _name = 'iac.rfq.quote.vendor'
    _inherit = 'iac.rfq'
    _table='iac_rfq'
    _order='id desc'

    @api.multi
    def buttonSubmit(self):
        for rfq_id in self.ids:
            # print rfq_id

            rfq_rec=self.env["iac.rfq"].browse(rfq_id)
            if rfq_rec.lt<=0:
                raise UserError('LTime must greater than zero')
            if rfq_rec.moq<=0:
                raise UserError('MOQ must greater than zero')
            if rfq_rec.mpq<=0:
                raise UserError('MPQ must greater than zero')
            if rfq_rec.input_price<=0 :
                raise UserError(_('Price must greater than zero!'))
            if rfq_rec.mpq>rfq_rec.moq:
                raise UserError(_('moq must greater than mpq!'))
            val = {}
            val['rfq_id'] = rfq_id
            val['create_by'] = self._uid
            val['create_timestamp'] = datetime.datetime.now()
            val['action_type'] = 'vendor confirm'
            self.env['iac.rfq.quote.history'].create(val)
        self.write({'state': 'replay'})

        action = self.env.ref('oscg_rfq.action_rfq_quote_vendor')
        action_window={
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'view_type': action.view_type,
            'view_mode':"tree,form",
            # 'target': action.target,
            'target': 'current',
            'res_model': action.res_model,
            # 'auto_refresh':1,
            'domain':action.domain,
            # 'view_id': self.env.ref('oscg_rfq.view_iac_rfq_quote_vendor_list').id,
            }
        return action_window

    @api.multi
    def write(self,vals):
        result=super(IacRfqQuoteVendor,self).write(vals)
        return result

    @api.model
    def create(self,vals):
        result=super(IacRfqQuoteVendor,self).create(vals)
        return result




class IacRfqImportQuoteCmWizard(models.TransientModel):
    _name = 'iac.rfq.import.quote.cm.wizard'
    _inherit = 'iac.file.import'


    @api.multi
    def action_upload_file(self):
        """
        上传文件按钮入口
        :return:
        """
        model_name="iac.rfq.import.quote"

        fields = ['id','plant_id','vendor_id','part_code','currency_id','input_price','valid_from','valid_to','price_control','note','vendor_part_no','tax']
        process_result,import_result,action_url=super(IacRfqImportQuoteCmWizard,self).import_file(model_name,fields)
        if process_result==False:
            return action_url

        #导入成功的情况下,转入数据到正式表中
        file_vals = {
            'name': 'import-error-messages',
            'datas_fname': 'import-error-messages.xls',
            'description': 'rfq import error messages',
            'type': 'binary',
            'db_datas': self.file,
            }
        file_rec = self.env['ir.attachment'].create(file_vals)
        import_vals={
            'state': 'cm_uploaded',
            'cm_file_id':file_rec.id,
            }
        ids=import_result["ids"]
        #这里的res_model是由action 的context 传入,代表目标表模型
        self.env[self.res_model].browse(ids).write(import_vals)

        #获取当前AS角色的source_code 列表

        for rfq_line in self.env[self.res_model].browse(ids):
            #校验source code 是否一致
            #if rfq_line.division_id.id not in self.env.user.division_id_list:
            #    raise UserError('Part no is (%s),Division Code is (%s) access dined' %(rfq_line.part_id.part_no,rfq_line.part_id.division_id.division))
            #校验厂别是否一致
            if rfq_line.plant_id.id not in self.env.user.plant_id_list:
                raise UserError('Plant Code is (%s) access dined' %(rfq_line.plant_id.plant_code,))
            rfq_line.apply_quote_import()

        return self.env['warning_box'].info(title=u"提示信息", message=u"导入数据操作成功！")


    def validate_parsed_data(self,data,import_fields):
        """
        校验刚刚通过解析的数据,子类可以重写当前函数,实现自定义的解析
        返回值有2个
        1   第一个表示校验是否成功
        2   错误信息列表
        :return:
        """
        ex_message_list=[]
        for num,data_line in enumerate(data):
            field_index=import_fields.index("input_price")
            field_val=data_line[field_index]

            process_result,float_vals=is_float_valid(field_val)
            if process_result==False:
                err_msg=u'小数位数不能超过6位或者非法字符串,小数值位 ( %s )'%( field_val)
                process_result=False
                ex_message_vals={
                    "message":err_msg,
                    'rows':{
                        "from":num,
                        "to":num,
                        }
                }
                ex_message_list.append(ex_message_vals)

        if len(ex_message_list)>0:
            return False,ex_message_list
        return True,[]

    def validate_imported_data(self,import_result):
        """
        校验刚刚通过导入的的数据,子类可以重写当前函数,实现自定义的校验过程
        1   第一个表示校验是否成功
        2   错误信息列表
        :return:
        """
        return True,[]

    @api.multi
    def action_download_file(self):
        file_dir=self.env["muk_dms.directory"].search([('name','=','file_template')],limit=1,order='id desc')
        if not file_dir.exists():
            raise UserError('File dir file_template does not exists!')
        file_template=self.env["muk_dms.file"].search([('filename','=','cm_quote_upload.xls')],limit=1,order='id desc')
        if not file_template.exists():
            raise UserError('File Template with name ( %s ) does not exists!'%("cm_quote_upload.xls",))
        action = {
            'type': 'ir.actions.act_url',
            'url': '/dms/file/download/%s'%(file_template.id,),
            'target': 'new',
        }
        return action