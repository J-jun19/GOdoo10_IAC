# -*- coding: utf-8 -*-
#修正曹工代码的耦合性,重构代码
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
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import ustr
_logger = logging.getLogger(__name__)



class IacFileImport(models.TransientModel):
    _name = 'iac.file.import'
    _inherit = 'base_import.import'
    _rec_name = 'file_name'

    def get_action_url(self,file_data, messages=None):
        """
        根据导入odoo模型的返回结果,输出错误信息文件,推送一个文件到浏览器端
        :param db_data:
        :param messages:
        :return:
        """
        input = StringIO()
        input.write(file_data)
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

    @api.multi
    def import_file(self,model_name,fields):
        """
        点击确认上传按钮时触发
        需要传入模型名称和字段列表
        :return:
        """
        self.ensure_one()
        if self.file==None:
            raise UserError("Must specific a file to upload!")
        self.file = base64.decodestring(self.file)
        options = {u'datetime_format': u'', u'date_format': u'%Y-%m-%d', u'keep_matches': False, u'encoding': u'utf-8', u'fields': [], u'quoting': u'"', u'headers': True, u'separator': u',', u'float_thousand_separator': u',', u'float_decimal_separator': u'.', u'advanced': False}
        process_result,import_result,action_url=self.import_to_model(model_name,fields,options)
        return process_result,import_result,action_url


    @api.multi
    def import_to_model(self,model_name, fields, options):
        """
        当前文件对象进行数据解析，数据导入操作
        并且返回字典类型格式的导入结果,如果导入过程中存在错误
        会在返回字典中记录错误信息和行号
        返回值有3个
        1   处理成功失败,过程中存在错误为失败
        2   处理的结果对象
        3   处理错误的时候回返回 action_url对象
        :param fields:
        :param options:

        :return:
        """
        self.ensure_one()

        #解析文件格式到集合对象中
        data=[]
        import_fields=[]
        try:
            data, import_fields = self._convert_import_data(fields, options)
            #王宁新增的代码回导致导入最大可交亮异常，先注释掉
            #for item in data:
            #    if item[2].isdigit():
            #        if len(item[2]) <= 10:
            #            final_num = item[2].zfill(10)
            #    item[2] = final_num

        except:
            traceback.print_exc()
            raise UserError("Upload file format is not valid!")
        try:
            import_fields.append('file_line_no')
            #为每一行数据增加行号,为每一行数据增加错误信息数据,默认为空
            line_no=1
            for data_line in data:
                data_line.append(line_no)
                data_line.append([])
                line_no=line_no+1


            #对数据进行目标格式转化操作
            process_result,data,ex_message_list = self._parse_import_data(data, import_fields, options)

            #进行自定义解析,出现异常的情况下，需要返回错误文件url
            process_result,ex_message_list=self.validate_parsed_data(data,import_fields)
            if process_result==False:
                action_url=self.get_action_url(self.file,ex_message_list)
                process_result,False,action_url
                return process_result,False,action_url

            #对导入的数据进行自定义业务逻辑解析

            #如果解析过程存在错误,那么生成错误文件后数据
            if process_result==False:
                #根据解析错误信息构建 message_list 信息
                action_url=self.get_action_url(data,ex_message_list)
                return process_result,False,action_url


            #解析过程正常,开始导入数据
            self._cr.execute('SAVEPOINT import')
            _logger.info('importing %d rows...', len(data))
            import_result = self.env[self.res_model].with_context(import_file=True).load(import_fields, data)
            _logger.info('done')
            self._cr.execute('RELEASE SAVEPOINT import')

            if "messages" in import_result and len(import_result["messages"])>0:
                process_result=False
                action_url=self.get_action_url(self.file,import_result["messages"])

                return process_result,import_result,action_url

            #进行自定义业务校验,是指从数据库层面进行业务校验
            process_result,ex_message_list=self.sudo().validate_imported_data(import_result)
            if process_result==False:
                action_url=self.get_action_url(self.file,ex_message_list)
                return process_result,import_result,action_url

            return process_result,import_result,False

        except:
            traceback.print_exc()
            raise UserError(traceback.format_exc())

    @api.model
    def _parse_float_from_data(self, data, index, name, options):
        """
        解析数据集合中的全部数值类型字段
        返回值有2个
        1   解析过程是否存在错误
        2   解析后的数据结果
        3   异常信息的列表
        :param data:
        :param index:
        :param name:
        :param options:
        :return:
        """
        process_result=True
        thousand_separator = options.get('float_thousand_separator', ' ')
        decimal_separator = options.get('float_decimal_separator', '.')

        ex_message_list=[]
        for num, line in enumerate(data):
            if not line[index]:
                continue
            #避免科学计数法导致问题
            float_val=float(line[index])
            line[index]="%f"%(float_val,)
            line[index] = line[index].replace(thousand_separator, '').replace(decimal_separator, '.')
            old_value = line[index]
            line[index] = self._remove_currency_symbol(line[index])
            if line[index] is False:
                #raise ValueError(_("Column %s contains incorrect values (value: %s)" % (name, old_value)))

                err_msg=_("Column %s contains incorrect values (value: %s)" % (name, old_value))
                process_result=False
                ex_message_vals={
                    "message":err_msg,
                    'rows':{
                        "from":num,
                        "to":num,
                        }
                }
                ex_message_list.append(ex_message_vals)
        return process_result,ex_message_list

    @api.multi
    def _parse_import_data(self, data, import_fields, options):
        """
        解析导入的数据,发生异常的情况下,输出到异常信息字段列表中
        返回值有2个
        1 解析过程是否存在错误
        2 解析后的数据集合
        3 解析后的发生的错误信息列表
        :param data:
        :param import_fields:
        :param options:
        :return:
        """
        # Get fields of type date/datetime
        ex_message_list=[]
        process_result=True

        all_fields = self.env[self.res_model].fields_get()
        for name, field in all_fields.iteritems():
            if field['type'] in ('date', 'datetime') and name in import_fields:
                # Parse date
                index = import_fields.index(name)
                dt = datetime.datetime
                server_format = DEFAULT_SERVER_DATE_FORMAT if field['type'] == 'date' else DEFAULT_SERVER_DATETIME_FORMAT

                if options.get('%s_format' % field['type'], server_format) != server_format:
                    user_format = ustr(options.get('%s_format' % field['type'])).encode('utf-8')
                    for num, line in enumerate(data):
                        if line[index]:
                            try:
                                line[index] = dt.strftime(dt.strptime(ustr(line[index]).encode('utf-8'), user_format), server_format)
                            except ValueError, e:
                                traceback.print_exc()
                                err_msg=_("Column %s contains incorrect values. Error in line %d: %s") % (name, num + 1, ustr(e.message))
                                process_result=False
                                ex_message_vals={
                                    "message":err_msg,
                                    'rows':{
                                        "from":num,
                                        "to":num,
                                    }
                                }
                                ex_message_list.append(ex_message_vals)
                                #raise ValueError(_("Column %s contains incorrect values. Error in line %d: %s") % (name, num + 1, ustr(e.message)))
                            except Exception, e:
                                traceback.print_exc()
                                err_msg=_("Error Parsing Date [%s:L%d]: %s") % (name, num + 1, ustr(e.message))
                                process_result=False
                                ex_message_vals={
                                    "message":err_msg,
                                    'rows':{
                                        "from":num,
                                        "to":num,
                                        }
                                }
                                ex_message_list.append(ex_message_vals)
                                #raise ValueError(_("Error Parsing Date [%s:L%d]: %s") % (name, num + 1, ustr(e.message)))

            elif field['type'] in ('float', 'monetary') and name in import_fields:
                # Parse float, sometimes float values from file have currency symbol or () to denote a negative value
                # We should be able to manage both case
                index = import_fields.index(name)


                process_result,ex_message_list=self._parse_float_from_data(data, index, name, options)
        return process_result,data,ex_message_list




    def validate_parsed_data(self,data,import_fields):
        """
        校验刚刚通过解析的数据,子类可以重写当前函数,实现自定义的解析
        返回值有2个
        1   第一个表示校验是否成功
        2   错误信息列表
        :return:
        """
        return True,[]

    def validate_imported_data(self,import_result):
        """
        校验刚刚通过导入的的数据,子类可以重写当前函数,实现自定义的校验过程
        1   第一个表示校验是否成功
        2   错误信息列表
        :return:
        """
        return True,[]
