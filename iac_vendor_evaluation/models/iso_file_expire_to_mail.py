# -*- coding: utf-8 -*-

from odoo import models, fields, api
# from odoo import models
from datetime import datetime
import traceback
from odoo.odoo_env import odoo_env


class IsoFileExpireToMail(models.Model):

    _name = 'iac.iso.file.expire.to.mail'
    _auto = False

    @odoo_env
    @api.model
    def job_iso_expire_to_vendor_buyer(self):
        """
        ISO文件的过期时间在接近一个月，三个月，半年的时候
        给厂商和采购发邮件进行提醒
        :return:
        """

        id_obj = self.env['iac.attachment.type'].search([('sub_group','=','iso')])
        id_list = []
        for id_item in id_obj:
            id_list.append(id_item.id)

        # print tuple(id_list)
        self._cr.execute(""" SELECT * from iac_vendor_register_attachment 
                            where file_id is not null and expiration_date is not NULL
                            AND type in %s
                            and (expiration_date-CURRENT_DATE BETWEEN 27 and 30
                            or expiration_date-CURRENT_DATE BETWEEN 88 and 90
                            or expiration_date-CURRENT_DATE BETWEEN 178 and 180) """,(tuple(id_list),))

        result_all = self.env.cr.dictfetchall()
        # result_all = self.env.cr.fetchall()
        vendor_reg_id_list = []
        for expire_item in result_all:
            if expire_item['vendor_reg_id']:
                vendor_reg_id_list.append(expire_item['vendor_reg_id'])
            else:
                pass
        vendor_reg_objs = self.env['iac.vendor.register'].browse(vendor_reg_id_list)

        vendor_id_list = []
        for vendor_reg_obj in vendor_reg_objs:
            if vendor_reg_obj.vendor_id.id and vendor_reg_obj.vendor_id.id not in vendor_id_list:
                vendor_id_list.append(vendor_reg_obj.vendor_id.id)
            else:
                pass
        vendor_objs = self.env['iac.vendor'].browse(vendor_id_list)

        for vendor_obj in vendor_objs:
            buyer_email = ""
            sales_email = vendor_obj.vendor_reg_id.sales_email
            other_emails = vendor_obj.vendor_reg_id.other_emails
            body_list = []
            for expire_vendor in result_all:
                vendor_code = self.env['iac.vendor.register'].browse(expire_vendor['vendor_reg_id']).vendor_code
                attachment_type = self.env['iac.attachment.type'].browse(expire_vendor['type'])
                if vendor_code == vendor_obj.vendor_code and vendor_obj.buyer_email:
                    if vendor_obj.buyer_email != buyer_email:
                        buyer_email += vendor_obj.buyer_email
                    else:
                        pass
                    # 写body
                    expire_time = datetime.now().strptime(expire_vendor['expiration_date'],"%Y-%m-%d")
                    today_time = datetime.now().strptime(datetime.now().strftime("%Y-%m-%d"),"%Y-%m-%d")
                    expire_days = (expire_time - today_time).days

                    print expire_days,type(expire_days)
                    expire_list = [str(vendor_obj.vendor_code),vendor_obj.name,'ISO',attachment_type.description,
                                   expire_vendor['expiration_date'],str(expire_days)]
                    body_list.append(expire_list)
            if buyer_email != "":
                if not sales_email and not other_emails:
                    email = buyer_email
                elif sales_email and not other_emails:
                    email = buyer_email + ';' + sales_email
                elif other_emails and not sales_email:
                    email = buyer_email + ';' + other_emails
                else:
                    email = buyer_email + ';' + sales_email + ';' + other_emails

            else:
                if not sales_email and not other_emails:
                    email = 'Zhang.Pei-Wu@iac.com.tw'+';'+'Wang.Ningg@iac.com.tw'+';'+'jiang.shier@iac.com.tw'
                elif sales_email and not other_emails:
                    email = sales_email
                elif other_emails and not sales_email:
                    email = other_emails
                else:
                    email = sales_email + ';' + other_emails

            self.env['iac.email.pool'].button_to_mail('iac-ep_support@iac.com.tw', email, "","ISO certificate is expiring",
                    ['Vendor Code', 'Vendor Name', 'Doc Type', 'Description','Expiration Date', 'Days before'], body_list, 'ISO file expire alert')

