# -*- coding: utf-8 -*-
from odoo import models, fields, api
# from odoo import models
from datetime import datetime
import traceback
from odoo.odoo_env import odoo_env


class IacBulletinToVendor(models.Model):

    _name = 'iac.bulletin.to.vendor.publish'

    @odoo_env
    def job_bulletin_to_vendor(self):
        """
        自动发送15天报关到期的公告job程式
        :return:
        """
        """
        1.从iac.custom.data.unfinished表中捞出15天内到期的资料
        2.利用原有的发公告的方式insert公告内容
        3.job发送
        """

        # 1.从iac.custom.data.unfinished表中所有资料(添加最后报关时间大于今日的日期的卡控)
        # time = self.env['iac.custom.data.unfinished'].search([('vendor_code','=','370001')]).last_entry_time
        # print time,type(time)
        unfinished_object = self.env['iac.custom.data.unfinished.pub'].search([
                '&',
                ('last_entry_time', '>', str(datetime.now())),
                ('entry_apply_no', '=', False),
                # ('entry_apply_no', '!=', 'null')
            ], order='vendor_code asc,delivery asc,item_no asc')
        print unfinished_object

        # 2.循环遍历表中得到表中捞出15天内到期的资料
        vendor_id_list = []
        for unfinished_one in unfinished_object:
            vendor_id = unfinished_one.vendor_id.id
            if vendor_id not in vendor_id_list and vendor_id is not False:
                vendor_id_list.append(vendor_id)
        print vendor_id_list

        for vendor_id_one in vendor_id_list:
            # str_header_row = '<tr height="20">' \
            #                 + '<td width="64"  bgcolor="#CCCCCC" align="left">Vendor Code</td>' \
            #                 + '<td width="73" bgcolor="#CCCCCC" align="left">海關系統廠商編碼</td>' \
            #                 + '<td width="177" align="left" bgcolor="#CCCCCC">廠商名稱</td>' \
            #                 + '<td width="111" align="left" bgcolor="#CCCCCC">送货单号</td>' \
            #                 + '<td width="26" align="left" bgcolor="#CCCCCC">明细单号</td>' \
            #                 + '<td width="151" align="left" bgcolor="#CCCCCC">入区时间</td>' \
            #                 + '<td width="60" align="left" bgcolor="#CCCCCC">最後報關時間</td>' \
            #                 + '<td width="142" align="left" bgcolor="#CCCCCC">货物品名</td>' \
            #                 + '<td width="98" align="left" bgcolor="#CCCCCC">货号</td>' \
            #                 + '<td width="110" align="left" bgcolor="#CCCCCC">数量</td>' \
            #                 + '<td width="90" align="left" bgcolor="#CCCCCC">报关金额</td>' \
            #                 + '<td width="100" align="left" bgcolor="#CCCCCC">电子底账序号</td>' \
            #                 + '<td width="64" align="left" bgcolor="#CCCCCC">退运数量</td>' \
            #                 + '<td width="81" align="left" bgcolor="#CCCCCC">商品编码</td>' \
            #                 + '<td width="87" align="left" bgcolor="#CCCCCC">附加编码</td>' \
            #                 + '<td width="125" align="left" bgcolor="#CCCCCC">报关申请书</td>' \
            #                 + '<td width="93" align="left" bgcolor="#CCCCCC">报关单号</td>' \
            #                 + '</tr>'
            str_header_row = '<tr height="20">' \
                             + '<td width="64" height="20" align="left" style="background-color: rgb(160, 160, 160)">Vendor Code</td>' \
                             + '<td width="73" align="left" style="background-color: rgb(160, 160, 160)">海關系統廠商編碼</td>' \
                             + '<td width="177" align="left" style="background-color: rgb(160, 160, 160)">廠商名稱</td>' \
                             + '<td width="111" align="left" style="background-color: rgb(160, 160, 160)">送货单号</td>' \
                             + '<td width="26" align="left" style="background-color: rgb(160, 160, 160)">明细单号</td>' \
                             + '<td width="151" align="left" style="background-color: rgb(160, 160, 160)">入区时间</td>' \
                             + '<td width="60" align="left" style="background-color: rgb(160, 160, 160)">最後報關時間</td>' \
                             + '<td width="142" align="left" style="background-color: rgb(160, 160, 160)">货物品名</td>' \
                             + '<td width="98" align="left" style="background-color: rgb(160, 160, 160)">货号</td>' \
                             + '<td width="110" align="left" style="background-color: rgb(160, 160, 160)">数量</td>' \
                             + '<td width="90" align="left" style="background-color: rgb(160, 160, 160)">报关金额</td>' \
                             + '<td width="100" align="left" style="background-color: rgb(160, 160, 160)">电子底账序号</td>' \
                             + '<td width="64" align="left" style="background-color: rgb(160, 160, 160)">退运数量</td>' \
                             + '<td width="81" align="left" style="background-color: rgb(160, 160, 160)">商品编码</td>' \
                             + '<td width="87" align="left" style="background-color: rgb(160, 160, 160)">附加编码</td>' \
                             + '<td width="125" align="left" style="background-color: rgb(160, 160, 160)">报关申请书</td>' \
                             + '<td width="93" align="left" style="background-color: rgb(160, 160, 160)">报关单号</td>' \
                             + '</tr>'
            print str_header_row

            unfinished_more = self.env['iac.custom.data.unfinished.pub'].search(['&',('vendor_id','=',vendor_id_one),('entry_apply_no', '=', False)])
            for unfinished_one in unfinished_more:
                if not unfinished_one.vendor_code or not unfinished_one.manu_no:
                    continue
                # 最后期限
                last_time = unfinished_one.last_entry_time #str类型
                last_date = datetime.strptime(last_time,'%Y-%m-%d %H:%M:%S')
                # 当天日期
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                now_date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                # 相减如果小于15天就发公告
                delta= last_date - now_date
                delta_days = delta.days
                if delta_days <= 15 and unfinished_one.vendor_id.id == vendor_id_one:

                    # 先将公告写入到iac_bulletin表中
                    # today_str = datetime.now().strftime('%Y-%m-%d')
                    vendor_code = unfinished_one.vendor_code
                    manu_no = unfinished_one.manu_no
                    manu_name = unfinished_one.manu_name
                    delivery = unfinished_one.delivery
                    item_no = unfinished_one.item_no
                    transit_time = unfinished_one.transit_time
                    last_entry_time = unfinished_one.last_entry_time
                    g_name = unfinished_one.g_name
                    part_no = unfinished_one.part_no
                    quantity_in = unfinished_one.quantity_in
                    amount = unfinished_one.amount
                    g_no = unfinished_one.g_no
                    quantity_back = unfinished_one.quantity_back
                    sku = unfinished_one.sku
                    additional_code = unfinished_one.additional_code
                    entry_apply_no = unfinished_one.entry_apply_no
                    pre_entry_no = unfinished_one.pre_entry_no

                    # 拼接公告contens html
                    str_body_row = '<tr height="20">' \
                                    + '<td height="20" align="left" >' + str(vendor_code) + '</td>' \
                                    + '<td align="left" >' + str(manu_no) + '</td>' \
                                    + '<td align="left" >' + str(manu_name) + '</td>' \
                                    + '<td align="left" >' + str(delivery) + '</td>' \
                                    + '<td align="left" >' + str(item_no) + '</td>' \
                                    + '<td align="left" >' + str(transit_time) + '</td>' \
                                    + '<td align="left" >' + str(last_entry_time) + '</td>' \
                                    + '<td align="left" >' + str(g_name) + '</td>' \
                                    + '<td align="left" >' + str(part_no) + '</td>' \
                                    + '<td align="left" >' + str(quantity_in) + '</td>' \
                                    + '<td align="left" >' + str(amount) + '</td>' \
                                    + '<td align="left" >' + str(g_no) + '</td>' \
                                    + '<td align="left" >' + str(quantity_back) + '</td>' \
                                    + '<td align="left" >' + str(sku) + '</td>' \
                                    + '<td align="left" >' + str(additional_code) + '</td>' \
                                    + '<td align="left" >' + str(entry_apply_no) + '</td>' \
                                    + '<td align="left" >' + str(pre_entry_no) + '</td>' \
                                    + '</tr>'
                    print str_body_row
                    str_header_row += str_body_row
                    print str_header_row
            str_body_html = '<table width="2200" cellpadding="0" cellspacing="0" border="1">' \
                            + str_header_row + '</table>'
            print str_body_html
            today_str = datetime.now().strftime('%Y-%m-%d')
            # if delta_days <= 15 and unfinished_one.vendor_id.id == vendor_id_one:

            # unfinished_search_one = self.env['iac.custom.data.unfinished.pub'].search([('vendor_id', '=', vendor_id_one)],order='id asc',limit=1)
            # if unfinished_search_one.vendor_code and unfinished_search_one.manu_no:

            if str_header_row.endswith('<td width="93" align="left" style="background-color: rgb(160, 160, 160)">报关单号</td></tr>'):
                continue
            bulletin_vals = {
                'name': '國內物資未報關明細-'+today_str,
                'start_date': today_str,
                'end_date': today_str,
                'is_all': '',
                'white_id': '',
                'send_mail': True,
                'send_mail_freq': 0,
                'subject': '國內物資未報關明細-'+today_str,
                'body': str_body_html,
                'state': 'draft'

            }
            try:
                bulletin_to_vendor_one = self.env['iac.bulletin'].create(bulletin_vals)
                bulletin_to_vendor_one.env.cr.commit()
            except:
                self.env.cr.rollback()
                traceback.print_exc()
            publish_id = bulletin_to_vendor_one.id

            # 将公告写入到iac_bulletin_publish表中去
            publish_vals = {
                'bulletin_id': publish_id,
                'subject': bulletin_to_vendor_one.subject,
                'body': bulletin_to_vendor_one.body,
                'start_date': bulletin_to_vendor_one.start_date,
                'end_date': bulletin_to_vendor_one.end_date,
                'send_mail': True,
                'send_mail_freq': 0,
                'vendor_id': vendor_id_one
            }

            try:
                publish_to_vendor_one = self.env['iac.bulletin.publish'].create(publish_vals)
                bulletin_to_vendor_one.write({"state": "published"})
                publish_to_vendor_one.env.cr.commit()
                # job发布完成更新状态


            except:
                self.env.cr.rollback()
                traceback.print_exc()

            # 发完公告继续发送邮件给vendor
            try:
                print vendor_id_one
                email = self.env['iac.vendor.register'].search([('vendor_id', '=', vendor_id_one)]).other_emails
                print email
                if str(email) is "":
                    email_bulletin_object = self.env['iac.bulletin'].search([],order='id desc', limit=1)
                    print email_bulletin_object
                    email_bulletin_object.write({"send_mail": False})
                    email_bulletin_object.env.cr.commit()
                    email_bulletin_pub_object = self.env['iac.bulletin.publish'].search([], order='id desc', limit=1)
                    email_bulletin_pub_object.write({"send_mail": False})
                    email_bulletin_pub_object.env.cr.commit()
                else:
                    self.env['iac.email.pool'].button_to_mail('iac-ep_support@iac.com.tw', email, "",
                                                          '國內物資未報關明細-'+today_str, ['请及时前往IAC Supplier Portal首页点击Bulletin查看15天內報關期限到期的資料'], [], 'RELEASE_BULLETIN_TO_VENDOR')
            except:
                self.env.cr.rollback()
