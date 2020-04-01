# -*- coding: utf-8 -*-
import pytz
import time
import odoo
from datetime import datetime
from odoo import models, fields, api,odoo_env
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import pdb
from odoo.odoo_env import odoo_env
from functools import wraps
import  traceback
import threading
import logging
import base64
import psycopg2
import os.path
from odoo import SUPERUSER_ID
_logger = logging.getLogger(__name__)

class IacBulletin(models.Model):
    """
    公告信息
    """
    _name = "iac.bulletin"
    _order = 'id desc'

    white_id = fields.Many2one('iac.bulletin.white', string="White List")
    is_all = fields.Boolean(string="Is all", default=False)
    attachment_line_ids=fields.One2many('iac.bulletin.attachment','bulletin_id',string="Attachment Files")
    subject = fields.Char('Subject')
    body = fields.Html('Contents', default='', sanitize_style=True, strip_classes=True)
    name = fields.Char('Bulletin Name',index=True)
    start_date=fields.Date(string='Start Date')
    end_date=fields.Date(string='End Date')
    send_mail = fields.Boolean(string="Send Mail To Vendor", default=False)
    send_mail_freq = fields.Integer(string="Send Mail Freq")
    state=fields.Selection([('draft','Draft'),('published','Published')],string="Status",default="draft")
    #file_id = fields.Many2one('muk_dms.file', string="Attachment File", index=True)

    def button_to_publish(self):
        """
        生成发布公告的数据，可以选择多笔进行发布
        :return:
        """
        publish_ids=[]
        for bulletin_id in self.ids:
            bulletin_rec=self.env["iac.bulletin"].browse(bulletin_id)
            if bulletin_rec.state=="published":
                continue
            #对有白名单的公告信息进行发送
            if bulletin_rec.white_id.exists() and bulletin_rec.is_all==False:
                for while_line_rec in bulletin_rec.white_id.line_ids:
                    publish_vals={
                        "bulletin_id":bulletin_id,
                        "subject":bulletin_rec.subject,
                        "body":bulletin_rec.body,
                        "start_date":bulletin_rec.start_date,
                        "end_date":bulletin_rec.end_date,
                        "send_mail":bulletin_rec.send_mail,
                        "send_mail_freq":bulletin_rec.send_mail_freq,
                        "vendor_id":while_line_rec.vendor_id.id,
                    }
                    attachment_line_ids=[]
                    for attachment_rec in bulletin_rec.attachment_line_ids:
                        attachment_vals={
                            "bulletin_id":bulletin_id,
                            "file_id":attachment_rec.file_id.id,
                            "file_desc":attachment_rec.file_desc,
                            "vendor_id":while_line_rec.vendor_id.id,
                        }
                        attachment_line_ids.append((0,0,attachment_vals))
                    publish_vals["attachment_line_ids"]=attachment_line_ids
                    bulletin_publish_rec=self.env["iac.bulletin.publish"].create(publish_vals)
                    publish_ids.append(bulletin_publish_rec.id)
                    continue
                bulletin_rec.write({"state":"published"})
                #操作完成变更状态

            #对没有设定白名单的公告信息进行发送
            if bulletin_rec.is_all==True:
                vendor_rec_list=self.env["iac.vendor"].search([('state','in',['done'])])
                for vendor_rec in vendor_rec_list:
                    publish_vals={
                        "bulletin_id":bulletin_id,
                        "subject":bulletin_rec.subject,
                        "body":bulletin_rec.body,
                        "start_date":bulletin_rec.start_date,
                        "end_date":bulletin_rec.end_date,
                        "send_mail":bulletin_rec.send_mail,
                        "send_mail_freq":bulletin_rec.send_mail_freq,
                        "vendor_id":vendor_rec.id,
                    }
                    attachment_line_ids=[]
                    for attachment_rec in bulletin_rec.attachment_line_ids:
                        attachment_vals={
                            "bulletin_id":bulletin_id,
                            "file_id":attachment_rec.file_id.id,
                            "file_desc":attachment_rec.file_desc,
                            "vendor_id":vendor_rec.id,
                        }
                        attachment_line_ids.append((0,0,attachment_vals))
                    publish_vals["attachment_line_ids"]=attachment_line_ids
                    bulletin_publish_rec=self.env["iac.bulletin.publish"].create(publish_vals)
                    publish_ids.append(bulletin_publish_rec.id)
                    continue
                #操作完成变更状态
                bulletin_rec.write({"state":"published"})
        alter_msg=u"操作成功，共生成 %s 条公告信息" %(len(publish_ids),)
        return self.env['warning_box'].info(title=u"提示信息", message=alter_msg)


    def button_attach_file(self):
        """
        只能被po对象调用,弹出窗口增加PO的对应的附加文档
        :return:
        """
        #签核中的不运行变更文件内容
        if self.state in ['published']:
            raise UserError("Can not upload file when order state is published")

        po_dir_rec=self.env["muk_dms.directory"].search([('name','=','bulletin_attachment')],order='id desc',limit=1)
        if not po_dir_rec.exists():
            raise UserError("Dir 'bulletin_attachment' has not found")

        action = self.env.ref('iac_vendor_evaluation.action_view_form_iac_bulletin_attachment')

        add_item_context={
            "default_bulletin_id":self.id,
            "default_directory":po_dir_rec.id
            }

        action_window={
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'view_type': action.view_type,
            'view_mode': action.view_mode,
            'target':  "new",
            'context': add_item_context,
            'res_model': action.res_model,
            }
        return action_window


    @api.onchange('white_id')
    def _onchange_white_id(self):
        partner_ids = []
        self.partner_ids = []
        # 白名单
        vendor_group = self.env.ref('oscg_vendor.IAC_vendor_groups')
        if vendor_group:
            for item in self.white_id.line_ids:
                if item.vendor_id.user_id in vendor_group.users:
                    partner_ids.append(item.vendor_id.user_id.partner_id.id)
        self.partner_ids = partner_ids

    @api.onchange('is_all')
    def _onchange_is_all(self):
        partner_ids = []
        if self.is_all:# 全选
            self.partner_ids = []
            vendor_group = self.env.ref('oscg_vendor.IAC_vendor_groups')
            if vendor_group:
                partner_list = self.env['res.partner'].search([('active', '=', True), ('supplier', '=', True)])
                for item in partner_list:
                    if item.user_id in vendor_group.users:
                        partner_ids.append(item.id)
            self.partner_ids = partner_ids

        else:# 使用白名单
            if self.white_id:
                # 白名单
                vendor_group = self.env.ref('oscg_vendor.IAC_vendor_groups')
                if vendor_group:
                    for item in self.white_id.line_ids:
                        if item.vendor_id.user_id in vendor_group.users:
                            partner_ids.append(item.vendor_id.user_id.partner_id.id)
                self.partner_ids = partner_ids


class IacBulletinAttachment(models.Model):
    """
    公告相关的附件文档
    """
    _name = "iac.bulletin.attachment"
    _inherits = {'muk_dms.file': 'file_id'}
    bulletin_id = fields.Many2one('iac.bulletin', string="White List")
    file_id=fields.Many2one('muk_dms.file',string='File Info',required=True,ondelete='cascade',index=True)
    file_desc=fields.Char(string='File Description')
    memo=fields.Char(string='Memo')

    def button_to_unlink(self):
        if self.bulletin_id.state in ['to_approve','to_change']:
            raise UserError("Can not delete file when order state is to_approve or to_change")

        action = self.env.ref('iac_vendor_evaluation.action_view_list_iac_bulletin')
        bulletin_id = self.bulletin_id.id
        self.unlink()
        return {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'view_type': action.view_type,
            'view_mode': action.view_mode,
            'target': action.target,
            'domain':action.domain,
            #'context': "{'default_order_id': " + str(order_id) + "}",
            'res_model': action.res_model,
            'res_id':bulletin_id,
            }


    @api.multi
    def button_to_return(self):
        """返回到po change form"""
        action = self.env.ref('iac_vendor_evaluation.action_view_list_iac_bulletin')
        bulletin_id = self.bulletin_id.id

        return {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'view_type': action.view_type,
            'view_mode': action.view_mode,
            'target': action.target,
            'domain':action.domain,
            #'context': "{'default_order_id': " + str(order_id) + "}",
            'res_model': action.res_model,
            'res_id':bulletin_id,
            }


class IacBulletinWhite(models.Model):
    """
    公告白名单
    """
    _name = "iac.bulletin.white"
    _description = "Vendor Message White list"
    _order = 'id desc'

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
    line_ids = fields.One2many('iac.bulletin.white.line', 'white_id', string="White Lines")
    active = fields.Boolean('Active', default=True)


    @api.model
    def create(self, values):
        # 白名单去重vendor code
        line_ids = set()
        list_line_ids = []
        if values.get('line_ids', False):
            for line_id in values.get('line_ids', False):
                line_ids.add(line_id[2]['vendor_id'])
            for item in line_ids:
                list_line_ids.append([0, False, {'vendor_id': item}])
            values['line_ids'] = list_line_ids
        result = super(IacBulletinWhite, self).create(values)
        return result

    @api.multi
    def write(self, values):
        # 白名单去重vendor code
        line_ids = set()# 新添加去重
        list_line_add_ids = []# 新添加
        list_line_reserve_ids = []# 保留
        list_line_remove_ids = []# 删除
        if values.get('line_ids', False):
            for line_id in values.get('line_ids', False):
                if line_id[0] == 0:# 新添加
                    line_ids.add(line_id[2]['vendor_id'])
                elif line_id[0] == 4:# 保留
                    list_line_reserve_ids.append(line_id)
                elif line_id[0] == 2:# 删除
                    list_line_remove_ids.append(line_id)
            int_list_line_reserve_ids = [self.env['mail.message.white.line'].browse(x[1]).vendor_id.id for x in list_line_reserve_ids]
            for item in line_ids:
                if item not in int_list_line_reserve_ids:
                    list_line_add_ids.append([0, False, {'vendor_id': item}])
            values['line_ids'] = list_line_reserve_ids + list_line_add_ids + list_line_remove_ids

        result = super(IacBulletinWhite, self).write(values)
        return result

class IacBulletinWhiteLine(models.Model):
    """
    Vendor 公告白名单 Line
    """
    _name = "iac.bulletin.white.line"
    _description = "Vendor Message White Line"

    white_id = fields.Many2one('iac.bulletin.white', string="White Name")
    vendor_id = fields.Many2one('iac.vendor', string="Vendor", required=True, index=True)
    vendor_code = fields.Char(string="Vendor Code",  index=True)
    vendor_name = fields.Char(string="Vendor Name", )

class IacBulletinPublish(models.Model):
    """
    发布给vendor的公告信息
    """
    _name = "iac.bulletin.publish"
    _order = 'id desc'

    vendor_id = fields.Many2one('iac.vendor', string="Vendor Info")
    user_id = fields.Many2one('res.users', string="User Info")
    white_id = fields.Many2one('iac.bulletin.white', string="White List")
    bulletin_id = fields.Many2one('iac.bulletin', string="Bulletin Info")
    attachment_line_ids=fields.One2many('iac.bulletin.publish.attachment','publish_id',string="Attachment Files")
    subject = fields.Char('Subject')
    body = fields.Html('Contents', default='', sanitize_style=True, strip_classes=True)
    start_date=fields.Date(string='Start Date')
    end_date=fields.Date(string='End Date')
    send_mail = fields.Boolean(string="Send Mail To Vendor", default=False)
    send_mail_freq = fields.Integer(string="Send Mail Freq")

    @odoo_env
    @api.model
    def job_send_notify_mail(self):
        """
        根据公告的频率发送邮件
        :return:
        """
        cur_date_str=datetime.now().strftime("%Y-%m-%d")
        cur_date=datetime.now()
        domain=[(['send_mail','=',True])]
        domain+=[(['start_date','<=',cur_date_str])]
        domain+=[(['end_date','>=',cur_date_str])]
        domain+=[(['send_mail_freq','>',0])]

        bulletin_list=self.env["iac.bulletin.publish"].sudo().search(domain)
        for bulletin in bulletin_list:
            start_date=datetime.strptime(bulletin.start_date,"%Y-%m-%d")
            day_num=cur_date-start_date
            #当前第一天必定发送邮件
            if day_num.days==0:
                self._send_mail()
            else:
                #周期数为正整数，余数为0
                result=divmod(day_num.days,bulletin.send_mail_freq)
                if result[0]>=1 and result[1]==0:
                    self._send_mail()
        return True

    def _send_mail(self):
        """
        针对当前记录对象的数据进行通知邮件发送
        """
        try:
            template = self.env.ref("iac_vendor_evaluation.iac_bulletin_publish_notify_email")
            user_admin=self.env["res.users"].browse(SUPERUSER_ID)
            context={
                "system_email":user_admin.email
            }
            template.with_context(context).send_mail(self.id, force_send=True)
        except:
            traceback.print_exc()


class IacBulletinPublishAttachment(models.Model):
    """
    发布给vendor的公告信息
    """
    _inherits = {'muk_dms.file': 'file_id'}
    _name = "iac.bulletin.publish.attachment"
    vendor_id = fields.Many2one('iac.vendor', string="Vendor Info")
    user_id = fields.Many2one('res.users', string="User Info")
    bulletin_id = fields.Many2one('iac.bulletin', string="Bulletin Info")
    publish_id = fields.Many2one('iac.bulletin.publish', string="Vendor Info")
    white_id = fields.Many2one('iac.bulletin.white', string="White List", domain=[('active', '=', True)])
    file_id=fields.Many2one('muk_dms.file',string='Attachment File',required=True,ondelete='cascade',index=True)
    file_desc=fields.Char(string='File Description')
    memo=fields.Char(string='Memo')

class IacBulletinWhiteUpload(models.TransientModel):
    _name = 'iac.bulletin.white.upload'
    _inherit = 'base_import.import'

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")

    @api.multi
    def action_download_file(self):
        file_dir=self.env["muk_dms.directory"].search([('name','=','file_template')],limit=1,order='id desc')
        if not file_dir.exists():
            raise UserError('File dir file_template does not exists!')
        file_template=self.env["muk_dms.file"].search([('filename','=','bulletin_white.xls')],limit=1,order='id desc')
        if not file_template.exists():
            raise UserError('File Template with name ( %s ) does not exists!'%("bulletin_white.xls",))
        action = {
            'type': 'ir.actions.act_url',
            'url': '/dms/file/download/%s'%(file_template.id,),
            'target': 'new',
        }
        return action

    @api.multi
    def action_confirm(self):
        self.ensure_one()
        self.file = base64.decodestring(self.file)

        # 判断文件类型
        file_extend = os.path.splitext(self.file_name)[1]
        if file_extend not in ('.xls', '.xlsx'):
            raise ValidationError(_(u'导入文件类型不是Excle格式，请使用导入模板编辑后重新导入！'))

        def _do_import(fields, options, Flag):
            result = self.do(fields, options, Flag)
            return result

        options = {u'datetime_format': u'', u'date_format': u'%Y-%m-%d', u'keep_matches': False, u'encoding': u'utf-8', u'fields': [], u'quoting': u'"', u'headers': True, u'separator': u',', u'float_thousand_separator': u',', u'float_decimal_separator': u'.', u'advanced': False}

        fields = ['vendor_code']
        result = _do_import(fields, options, False)

        if result['messages']:
            message = u'导入白名单完成，但有以下Vendor Code不存在或是非正常状态：%s' % result['messages']
            return self.env['warning_box'].info(title="message", message=message)
        else:
            action = {
                'name': _('White List'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'iac.bulletin.white',  # 跳转模型名称
                'res_id': result['white_id'],  # 跳转模型id
            }
            return action

    @api.multi
    def do(self, fields, options, dryrun=False):
        self.ensure_one()
        self._cr.execute('SAVEPOINT import')
        try:
            data, import_fields = self._convert_import_data(fields, options)
            # Parse date and float field
            data = self._parse_import_data(data, import_fields, options)
        except ValueError, error:
            return [{
                'type': 'error',
                'message': unicode(error),
                'record': False,
            }]
        _logger.info('importing %d rows...', len(data))

        # 拼装主从结构的白名单
        no_vendor_list = set()
        line_ids = []
        int_line_ids = set()
        for line in data:
            # 补齐10位vendor code
            vendor = self.env['iac.vendor'].search([('vendor_code', '=', line[0].zfill(10)), ('state', 'in', ('done', 'block'))], limit=1)
            if vendor:
                int_line_ids.add(vendor.id)
            else:
                no_vendor_list.add(line[0])
        for item in int_line_ids:
            line_ids.append((0, 0, {'vendor_id': item}))
        white_list = {
            'name': self.name,
            'description': self.description,
            'line_ids': line_ids
        }
        white_id = self.env['iac.bulletin.white'].create(white_list)
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
                self._cr.execute('RELEASE SAVEPOINT import')
        except psycopg2.InternalError:
            pass

        if no_vendor_list:
            messages = ','.join(list(no_vendor_list))
        else:
            messages = ''
        return {'messages': messages, 'white_id': white_id.id}
