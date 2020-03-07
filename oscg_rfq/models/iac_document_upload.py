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
import traceback
import math

_logger = logging.getLogger(__name__)



class DocumentUpload(models.TransientModel):
    _name = 'iac.document.upload'
    _inherit = 'base_import.import'
    _rec_name = 'file_name'

    # excel_file = fields.Binary('上传附件',filters='*.xls')
    code = fields.Selection([
                                ('1','Quote Import'),
                                ('2','AS RFQ Import'),
                                ('3','MM Upload'),
                                ('4','jitrule Import'),
                                ('5','ASN Import'),
                                ('6','MaxQty Import')
                            ],string='Import code')

    @api.multi
    def action_confirm(self):
        self.ensure_one()
        self.file = base64.decodestring(self.file)
        def _get_messages_file(db_data, messages=None):
            input = StringIO()
            input.write(db_data)
            wb = open_workbook(file_contents=input.getvalue())
            sheet = wb.sheet_by_index(0)

            output = StringIO()
            wb2 = xlwt.Workbook()
            sheet1 = wb2.add_sheet('sheet1',cell_overwrite_ok=True)
            # write header
            for i in xrange(sheet.ncols):
                sheet1.write(0, i, sheet.cell(0,i).value)
            sheet1.write(0,sheet.ncols,'message')
            # write messages
            r = 1
            for m in messages:
                for i in xrange(m.get('rows').get('from'),m.get('rows').get('to') + 1):
                    for j in xrange(sheet.ncols):
                        sheet1.write(r,j, sheet.cell(i+1,j).value)
                    sheet1.write(r,sheet.ncols,m.get('message'))
                    r += 1
            wb2.save(output)

            vals = {
                'name': 'import-error-messages',
                'datas_fname': 'import-error-messages.xls',
                'description': 'rfq import error messages',
                'type': 'binary',
                'db_datas': base64.encodestring(output.getvalue()),
                }
            file = self.env['ir.attachment'].create(vals)
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s/%s.xls' % (file.id,file.id,),
                'target': 'new',
                }

        def _do_import(fields,options,Flag,code):
            messages = self.do(fields, options, Flag, code)
            if messages:
                return _get_messages_file(self.file,messages)
            return True

        fields = []
        options = {u'datetime_format': u'', u'date_format': u'%Y-%m-%d', u'keep_matches': False, u'encoding': u'utf-8', u'fields': [], u'quoting': u'"', u'headers': True, u'separator': u',', u'float_thousand_separator': u',', u'float_decimal_separator': u'.', u'advanced': False}

        if self.code == '1': # Quote import
            fields = ['id','plant_id','vendor_id','part_code','currency_id','input_price','valid_from','valid_to','price_control','note','vendor_part_no','lt','moq','mpq','rw','cw','tax']
        if self.code == '2': # AS import
            fields = ['id','plant_id','vendor_id','part_code','currency_id','input_price','valid_from','valid_to','price_control','note','vendor_part_no']
        if self.code == '3': # MM import, moq/mpq/lt/cw/rw/tax
            fields = ['id','plant_id','vendor_id','part_code','currency_id','input_price','valid_from','valid_to','price_control','note','vendor_part_no','lt','moq','mpq','cw','rw','tax']
        if self.code == '4': # jitrule
            fields = ['id','vendor_id','plant_id','part_code','buyer_code','black_white_list','validate_from','validate_to']
        if self.code == '5': # iac.asn
            fields = ['plant_id','vendor_id','line_ids/po_id','line_ids/part_id','line_ids/asn_qty','line_ids/qty_per_carton']
        if self.code == '6': # asn.max
            fields = ['plant_id','vendor_id','material','maxqty']
        return _do_import(fields,options,False, self.code)

    @api.model
    def is_float_valid(self,float_val):
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
            return False
        else:
            return  True

    @api.multi
    def do(self, fields, options, dryrun=False, code = False):
        self.ensure_one()
        self._cr.execute('SAVEPOINT import')
        try:
            data, import_fields = self._convert_import_data(fields, options)

            #处理数字中含有科学计数法导致程序失败的问题
            if self.code in ['1','2','3']:
                for data_line in data:
                    field_index=fields.index("input_price")
                    field_val=data_line[field_index]
                    if 'e' in field_val:
                       float_vals= eval(field_val)
                       data_line[field_index]="%f"%(float_vals,)
                    str_val=''
                    str_val=field_val
                    if str_val.isdigit() and self.is_float_valid(float(field_val))==False:
                        raise UserError(u'小数位数不能超过6位,小数值位 ( %s )'%( field_val))
            # Parse date and float field
            data = self._parse_import_data(data, import_fields, options)

            if self.code=='1':
                #导入quote 的情况
                import_fields.append('file_line_no')
                #为每一行增加行号
                line_no=1
                for data_line in data:
                    data_line.append(line_no)
                    line_no=line_no+1

            if self.code=='2':
                import_fields.append('file_line_no')
                #为每一行增加行号
                line_no=1
                for data_line in data:
                    data_line.append(line_no)
                    line_no=line_no+1
            if self.code=='3':
                import_fields.append('file_line_no')
                #为每一行增加行号
                line_no=1
                for data_line in data:
                    data_line.append(line_no)
                    line_no=line_no+1

                import_ids=[]
                for data_line in data:
                    vals={}
                    #moq	mpq	lt	cw	rw	tax
                    vals["moq"]=float(data_line[fields.index("moq")])
                    vals["mpq"]=float(data_line[fields.index("mpq")])
                    vals["lt"]=int(data_line[fields.index("lt")])
                    vals["cw"]=data_line[fields.index("cw")]
                    vals["rw"]=data_line[fields.index("rw")]
                    vals["tax"]=data_line[fields.index("tax")]
                    vals["state"]="mm_updated"

                    rfq_line=self.env["iac.rfq.import.mm"].browse(int(data_line[fields.index("id")]))
                    if not rfq_line.exists():
                        error_msg="id not exists %s" %(data_line[fields.index("id")],)
                        return [{
                                    'type': 'error',
                                    'message': unicode(error_msg),
                                    'record': False,
                                    'rows':{
                                        'from':data_line[import_fields.index("file_line_no")]-1,
                                        'to':data_line[import_fields.index("file_line_no")]-1,
                                    }
                                    }]
                    #as_uploaded
                    if rfq_line.state!="as_uploaded":
                        error_msg="recored is not in valid state,id is %s" %(data_line[fields.index("id")],)
                        return [{
                                    'type': 'error',
                                    'message': unicode(error_msg),
                                    'record': False,
                                    'rows':{
                                        'from':data_line[import_fields.index("file_line_no")]-1,
                                        'to':data_line[import_fields.index("file_line_no")]-1,
                                        }
                                    }]

                    if rfq_line.input_price!=float(data_line[fields.index("input_price")]):
                        error_msg="can not change input_price,where id is( %s )" %(data_line[fields.index("id")],)
                        return [{
                                    'type': 'error',
                                    'message': unicode(error_msg),
                                    'record': False,
                                    'rows':{
                                        'from':data_line[import_fields.index("file_line_no")]-1,
                                        'to':data_line[import_fields.index("file_line_no")]-1,
                                        }
                                    }]

                    if rfq_line.valid_from!=data_line[fields.index("valid_from")]:
                        error_msg="can not change valid_from,where id is( %s )" %(data_line[fields.index("id")],)
                        return [{
                                    'type': 'error',
                                    'message': unicode(error_msg),
                                    'record': False,
                                    'rows':{
                                        'from':data_line[import_fields.index("file_line_no")]-1,
                                        'to':data_line[import_fields.index("file_line_no")]-1,
                                        }
                                    }]

                    if rfq_line.valid_to!=data_line[fields.index("valid_to")]:
                        error_msg="can not change valid_to,where id is( %s )" %(data_line[fields.index("id")],)
                        return [{
                                    'type': 'error',
                                    'message': unicode(error_msg),
                                    'record': False,
                                    'rows':{
                                        'from':data_line[import_fields.index("file_line_no")]-1,
                                        'to':data_line[import_fields.index("file_line_no")]-1,
                                        }
                                    }]

                    if rfq_line.vendor_id.vendor_code!=data_line[fields.index("vendor_id")]:
                        error_msg="can not change vendor_id,where id is( %s )" %(data_line[fields.index("id")],)
                        return [{
                                    'type': 'error',
                                    'message': unicode(error_msg),
                                    'record': False,
                                    'rows':{
                                        'from':data_line[import_fields.index("file_line_no")]-1,
                                        'to':data_line[import_fields.index("file_line_no")]-1,
                                        }
                                    }]

                    if rfq_line.plant_id.plant_code!=data_line[fields.index("plant_id")]:
                        error_msg="can not change plant_id,where id is( %s )" %(data_line[fields.index("id")],)
                        return [{
                                    'type': 'error',
                                    'message': unicode(error_msg),
                                    'record': False,
                                    'rows':{
                                        'from':data_line[import_fields.index("file_line_no")]-1,
                                        'to':data_line[import_fields.index("file_line_no")]-1,
                                        }
                                    }]

                    if rfq_line.part_code!=data_line[fields.index("part_code")]:
                        error_msg="can not change part_code,where id is( %s )" %(data_line[fields.index("id")],)
                        return [{
                                    'type': 'error',
                                    'message': unicode(error_msg),
                                    'record': False,
                                    'rows':{
                                        'from':data_line[import_fields.index("file_line_no")]-1,
                                        'to':data_line[import_fields.index("file_line_no")]-1,
                                        }
                                    }]

                    if rfq_line.currency_id.name!=data_line[fields.index("currency_id")]:
                        error_msg="can not change currency_id,where id is( %s )" %(data_line[fields.index("id")],)
                        return [{
                                    'type': 'error',
                                    'message': unicode(error_msg),
                                    'record': False,
                                    'rows':{
                                        'from':data_line[import_fields.index("file_line_no")]-1,
                                        'to':data_line[import_fields.index("file_line_no")]-1,
                                        }
                                    }]

                    rfq_line.write(vals)
                    rfq_line.apply_mm_update()
                    import_ids.append(int(data_line[fields.index("id")]))
                    #导入操作成功,要从这里返回
                return []

        except ValueError, error:
            traceback.print_exc()
            return [{
                        'type': 'error',
                        'message': unicode(error),
                        'record': False,
                        }]
        _logger.info('importing %d rows...', len(data))
        import_result = self.env[self.res_model].with_context(import_file=True).load(import_fields, data)
        _logger.info('done')

        # If transaction aborted, RELEASE SAVEPOINT is going to raise
        # an InternalError (ROLLBACK should work, maybe). Ignore that.
        # TODO: to handle multiple errors, create savepoint around
        #       write and release it in case of write error (after
        #       adding error to errors array) => can keep on trying to
        #       import stuff, and rollback at the end if there is any
        #       error in the results.
        try:
            if dryrun:
                self._cr.execute('ROLLBACK TO SAVEPOINT import')
            else:
                # update state
                ids = import_result.get('ids')
                if code and ids:
                    #quote导入的情况
                    if code=='1':
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
                        self.env[self.res_model].browse(ids).write(import_vals)
                        for rfq_line in self.env[self.res_model].browse(ids):
                            rfq_line.apply_quote_import()

                    #as 上传文件的情况下存储文件信息
                    if code == '2':
                        file_vals = {
                            'name': 'import-error-messages',
                            'datas_fname': 'import-error-messages.xls',
                            'description': 'rfq import error messages',
                            'type': 'binary',
                            'db_datas': self.file,
                            }
                        file_rec = self.env['ir.attachment'].create(file_vals)
                        import_vals={
                            'state': 'as_uploaded',
                            'as_file_id':file_rec.id,
                            }
                        self.env[self.res_model].browse(ids).write(import_vals)
                        for rfq_line in self.env[self.res_model].browse(ids):
                            if rfq_line.valid_from>rfq_line.valid_to:
                                raise UserError('valid_from can not grater then valid_to,name is: %s'%self.name)
                            #校验是否有重复数据
                            domain=[('state','in',['draft','sent','replay','wf_fail','wf_unapproved','wf_approved','sap_fail'])]
                            domain+=[('type','=','rfq')]
                            domain+=[('vendor_id','=',rfq_line.vendor_id.id)]
                            domain+=[('part_id','=',rfq_line.part_id.id)]
                            rfq_rec=self.env["iac.rfq"].search(domain,order='id desc',limit=1)
                            if rfq_rec.exists():
                                raise UserError('A RFQ  with same vendor and part already exists; name is %s'%rfq_rec.name)

                    # end jk
                self._cr.execute('RELEASE SAVEPOINT import')
        except psycopg2.InternalError:
            pass

        return import_result['messages']