# -*- coding: utf-8 -*-
from odoo import models, fields, api,_
from odoo.exceptions import UserError
import datetime
from xlrd import open_workbook
import base64

class MaterialMasterAsn(models.Model):
    """用在asn 相关,绕过记录规则权限筛选"""
    _name = "material.master.asn"
    _inherit="material.master"
    _table="material_master"
    _description = "Material Mater ASN"
    _order = 'id desc'


class AsnMaxQty(models.Model):
    _inherit = 'asn.maxqty'
    _order = 'id desc'
    _table='asn_maxqty'
    shipped_qty =fields.Integer('Shipped QTY',default=0)
    remained_qty =fields.Integer('Available Qty',compute='_compute_remained_qty')
    part_id = fields.Many2one('material.master.asn', string='Part No',compute = '_compute_fields',store=True)
    file_line_no=fields.Integer(string='File Line No')
    engineid = fields.Selection([("IACD","IACD"),("IACW","IACW")],string="Engineid",default="IACW")
    state=fields.Selection([('cancel','Cancel'),('done','Done')],string='State',default='done')
    last_max_qty_id=fields.Many2one('asn.maxqty',string='Last Max Qty')
    comments=fields.Text(string="Comments")
    part_id_inc = fields.Many2one('material.master.asn', string='Part No')
    asn_increase_line_ids=fields.One2many('iac.asn.max.qty.create.line','asn_max_qty_id',string='ASN Increase QTY Info')

    @api.multi
    @api.depends('material', 'plant_id')
    def _compute_fields(self):
        for r in self:
            if not r.plant_id.exists():
                raise UserError('Plant can not be Null!')
            part = self.env['material.master.asn'].search(
                [('plant_id', '=', r.plant_id and r.plant_id.id or False), ('part_no', '=', r.material)])
            r.part_id = part and part[0].id or False
            if r.material and not r.part_id:
                raise UserError('Part Code is not exist!')

    @api.one
    @api.depends('maxqty', 'shipped_qty')
    def _compute_remained_qty(self):
        inc_qty_sum=0
        for asn_inc_qty in self.asn_increase_line_ids:
            inc_qty_sum+=asn_inc_qty.increase_qty
        self.remained_qty = self.maxqty +inc_qty_sum- self.shipped_qty



    # ning update 190402 调整最大可交量抓取方式
    @api.model
    def max_kakong(self,vendor_id,part_id,vendor_code,part_no):
        max = self.env['iac.asn.max.qty.create.update'].search([('vendor_id', '=', vendor_id), ('part_id', '=', part_id),('state','=','done')],limit=1)
        if not max.exists():
            raise UserError(u'拥有卡控规则的情况下,没有配置最大可交量:vendor_code 是 ( %s );part_no 是 ( %s )' % (vendor_code, part_no,))
        if True:
            maxqty = max.available_qty

        return True, maxqty,max.id

    @api.model
    def asn_cancel_raise_max_qty(self,vendor_id,part_id,vendor_code,part_no,cancel_qty):
        """
        ASN  line cancel之后
            如果找不到最大可交量数据,那么新增一条最大可交量,数量为asn line 中减少的数量
            如果能够找到最大可交量数据,那么在最大可交量的shipped_qty中减去 asn line 中减少的数量
        返回值为3个
        1   布尔型,是否操作成功
        2   减少已经交付的数量后，得到的最大可交量
        3   最大可交量记录id
        :param vendor_id:
        :param part_id:
        :param vendor_code:
        :param part_no:
        :return:
        """
        asn_max_rec = self.env['asn.maxqty'].search([('vendor_id', '=', vendor_id), ('part_id', '=', part_id),('state','=','done')],limit=1)
        if not asn_max_rec.exists():
            vendor_rec=self.env["iac.vendor"].browse(vendor_id)
            max_qty_vals={
                "vendor_id":vendor_id,
                "part_id":part_id,
                "vendorcode":vendor_rec.vendor_code,
                "material":part_no,
                "plant_id":vendor_rec.plant.id,
                "plant":vendor_rec.plant.plant_code,
                "engineid":"IACW",
                "maxqty":cancel_qty,
            }
            asn_max_rec=self.env["asn.maxqty"].create(max_qty_vals)
            return True, asn_max_rec.remained_qty,asn_max_rec.id

        #如果最大可交量存在,减少已经交付的量
        new_shipped_qty=asn_max_rec.shipped_qty-cancel_qty
        asn_max_rec.write({"shipped_qty":new_shipped_qty})
        return True, asn_max_rec.remained_qty,asn_max_rec.id

    @api.model
    def proc_max_qty_rec(self,vendor_id,part_id,vendor_code,part_no,cancel_qty):
        """
        获取最大可交量记录
            如果找不到最大可交量数据,那么新增一条最大可交量,数量为减少的数量
            如果能够找到最大可交量数据,那么减少已交量来被动增加最大可交量
        返回值为3个
        1   布尔型,是否操作成功
        2   减少已经交付的数量后，得到的最大可交量
        3   最大可交量记录id
        :param vendor_id:
        :param part_id:
        :param vendor_code:
        :param part_no:
        :return:
        """
        asn_max_rec = self.env['asn.maxqty'].search([('vendor_id', '=', vendor_id), ('part_id', '=', part_id),('state','=','done')],limit=1)
        if not asn_max_rec.exists():
            vendor_rec=self.env["iac.vendor"].browse(vendor_id)
            max_qty_vals={
                "vendor_id":vendor_id,
                "part_id":part_id,
                "vendorcode":vendor_rec.vendor_code,
                "material":part_no,
                "plant_id":vendor_rec.plant.id,
                "plant":vendor_rec.plant.plant_code,
                "engineid":"IACW",
                "maxqty":cancel_qty,
            }
            asn_max_rec=self.env["asn.maxqty"].create(max_qty_vals)
            return True, asn_max_rec.remained_qty,asn_max_rec.id

        #如果最大可交量存在,减少已经交付的量
        new_shipped_qty=asn_max_rec.shipped_qty-cancel_qty
        asn_max_rec.write({"shipped_qty":new_shipped_qty})
        return True, asn_max_rec.remained_qty,asn_max_rec.id


    @api.one
    def minus_max_qty(self,minus_qty):
        """
        增加ASN数量,扣减当前记录的最大可交量
        :return:
        """
        #if self.remained_qty<minus_qty:
        #    raise UserError(u"最大可交量小于要扣减的可交量,目前最大可交量为 ( %s ),需要扣减 ( %s )",(self.remained_qty,minus_qty))
        #self.shipped_qty=self.shipped_qty+minus_qty

        vasl={
            "shipped_qty":self.shipped_qty+minus_qty,
            }
        self.write(vasl)
        # self.env.cr.commit()
    @api.one
    def add_max_qty(self,add_qty):
        """
        减少ASN数量,增加当前记录的最大可交量
        :return:
        """
        #if self.shipped_qty<abs(add_qty):
        #    raise UserError(u"ASN累计量不能小于零,目前ASN累积量为 ( %s ),需要扣减 ( %s )",(self.shipped_qty,add_qty))
        #self.shipped_qty=self.shipped_qty-add_qty
        vasl={
            "shipped_qty":self.shipped_qty-add_qty,
        }
        self.write(vasl)
        self.env.cr.commit()


    @api.onchange('vendor_id', 'part_id')
    def onchange_vendor_id_part_id(self):
        if not self.vendor_id.exists():
            return
        if not self.part_id.exists():
            return
        domain=[('vendor_id','=',self.vendor_id.id),('part_id','=',self.part_id.id)]
        domain+=[('state','=','done'),('id','!=',self.id)]
        last_max_qty=self.env["asn.maxqty"].search(domain,limit=1)
        if last_max_qty.exists():
            #r.remained_qty = r.maxqty +r.increase_qty- r.shipped_qty
            self.maxqty=last_max_qty.remained_qty
            self.remained_qty=last_max_qty.remained_qty
            self.engineid=last_max_qty.engineid
            self.increase_qty=0
            self.shipped_qty=0
            self.last_max_qty_id=last_max_qty
        else:
            self.engineid="IACW"

    @api.model
    def create(self,vals):
        result=super(AsnMaxQty,self).create(vals)
        super(AsnMaxQty,result).write({"part_id_inc":result.part_id.id})
        result._vaildate_record()
        update_vals={
            "state":"done",
            "division":result.part_id.division,
            "division_id":result.part_id.division_id.id,
        }
        super(AsnMaxQty,result).write(update_vals)
        if result.last_max_qty_id.exists():
            result.last_max_qty_id.write({'state':'cancel'})
        return result

    @api.model
    def return_asn_qty(self,vals):
        """
        返回最大可交量
        :param vals:
        :return:
        """
        vendor_id=vals.get("vendor_id")
        part_id=vals.get("part_id")
        max_rec = self.env['asn.maxqty'].search([('vendor_id', '=', vendor_id), ('part_id', '=', part_id),('state','=','done')],limit=1)
        if not max_rec.exists():
            max_asn_vals={
                "vendor_id":vendor_id,
                "part_id":part_id,
                "plant_id":vals.get("plant_id"),
                "material":vals.get("part_no"),
                "maxqty":vals.get("asn_qty"),
            }
            result=self.env["asn.maxqty"].create(max_asn_vals)
            return result
        else:
            max_rec.add_max_qty(vals.get("asn_qty"))
            return max_rec

    def _vaildate_record(self):
        """
        校验当前记录是否合法
        :return:
        """
        if not self.plant_id.exists():
            raise UserError("Plant can not be Null")
        if self.material==False:
            raise UserError("Part Code Can not be Null")
        if self.maxqty==0:
            raise UserError("Max Qty must greater than zero")
        if not self.vendor_id.plant.id==self.plant_id.id:
            raise UserError("Vendor Plant is not same with Plant")
        if self.part_id_inc.exists():
            if not self.part_id_inc.plant_id.id==self.plant_id.id:
                raise UserError("Part Plant is not same with Plant")



class purOrgData(models.Model):
    _inherit = 'pur.org.data'
    _rec_name = 'plant_code'


# 批量放量程序ning add 190325 begin
class AsnMaxQtyImportUpdateWizard(models.TransientModel):
    _name = 'asn.maxqty.import.update.wizard'

    file_name = fields.Char()
    file = fields.Binary()

    @api.multi
    def maxqty_download(self):
        file_dir = self.env["muk_dms.directory"].search([('name', '=', 'file_template')], limit=1, order='id desc')
        if not file_dir.exists():
            raise UserError('File dir file_template does not exists!')
        file_template = self.env["muk_dms.file"].search([('filename', '=', 'asn_max_qty_import.xls')], limit=1,
                                                        order='id desc')
        if not file_template.exists():
            raise UserError('File Template with name ( %s ) does not exists!' % ("asn_max_qty_import.xls",))
        action = {
            'type': 'ir.actions.act_url',
            'url': '/dms/file/download/%s' % (file_template.id,),
            'target': 'new',
        }
        return action


    @api.multi
    def maxqty_upload(self):
        # 轉資料的job正在執行,就不能執行程式20190419 ning add ___begin
        self._cr.execute("  select count(*) as job_count  from ep_temp_master.extractlog "
                         "  where extractname in ( select extractname from ep_temp_master.extractgroup "
                         "                                        where extractgroup = 'ASN' ) "
                         "      and extractstatus = 'ODOO_PROCESS'   ")
        for job in self.env.cr.dictfetchall():
            if job['job_count'] and job['job_count'] > 0:
                raise UserError(' 正在轉資料 ,請勿操作 ! ')
                # 轉資料的job正在執行,就不能執行程式20190419 ning add ___end
        excel_obj = open_workbook(file_contents=base64.decodestring(self.file))
        sheet_obj = excel_obj.sheet_by_index(0)
        error_str = ''
        error_num1 = ''
        error_num2 = ''
        error_num3 = ''
        error_num4 = ''
        error_num5 = ''
        error_num6 = ''
        error_num7 = ''
        error_num8 = ''
        error_flag = 0
        validate_list = []
        show_list=[]
        if sheet_obj.cell(0,0).value == 'plant_id' and sheet_obj.cell(0,4).value == 'comments':
            for rx in range(sheet_obj.nrows):
                if rx>=1:
                    plant_id = self.env['pur.org.data'].search([('plant_code','=',(sheet_obj.cell(rx,0).value).strip())]).id
                    vendor_id = self.env['iac.vendor.asn'].search(
                        [('vendor_code', '=', (sheet_obj.cell(rx, 1).value).strip())]).id
                    material_id = self.env['material.master.asn'].search(
                        [('part_no', '=', (sheet_obj.cell(rx, 2).value).strip()),('plant_id','=',plant_id)]).id
                    buyer_id = self.env['material.master.asn'].search(
                        [('part_no', '=', (sheet_obj.cell(rx, 2).value).strip()), ('plant_id', '=', plant_id)]).buyer_code_id.id
                    # 判断plant + vendor在vendor表是否存在
                    if not self.env['iac.vendor.asn'].search([('vendor_code','=',(sheet_obj.cell(rx,1).value).strip()),('plant','=',plant_id)]):
                        error_num1 = error_num1+str(rx+1)+','
                        error_flag=1
                    # 判断plant+material在material表中是否存在
                    if not self.env['material.master.asn'].search([('part_no','=',(sheet_obj.cell(rx,2).value).strip()),('plant_id','=',plant_id)]):
                        error_num2 = error_num2+str(rx+1)+','
                        error_flag=1
                    #判断材料是否在白名单上
                    # try:
                    #     flag, max_qty, max_qty_id = self.env["asn.jitrule"].kakong(vendor_id,
                    #                                                                buyer_id,
                    #                                                                material_id,
                    #                                                                (sheet_obj.cell(rx, 1).value).strip(),
                    #                                                                (sheet_obj.cell(rx, 2).value).strip())
                    # except:
                    #     flag = True
                    # if flag == False:
                    #     error_num8 = error_num8 + str(rx + 1) + ','
                    #     error_flag = 1
                    # comment必填
                    if not sheet_obj.cell(rx,4).value:
                        error_num6 = error_num6+str(rx+1)+','
                        error_flag=1
                    # plant + vendor + material是否有重复
                    plant_part_vendor_str = str((sheet_obj.cell(rx,0).value).strip())+\
                                            ','+str((sheet_obj.cell(rx, 1).value).strip())+\
                                            ','+str((sheet_obj.cell(rx,2).value).strip())
                    if plant_part_vendor_str not in validate_list:
                        validate_list.append(plant_part_vendor_str)
                    else:
                        show_list.append(plant_part_vendor_str)


                    if isinstance(sheet_obj.cell(rx,3).value , unicode):
                        raise UserError('请检查放量数栏位是否有非数字内容,并设定该列为数字格式')
                    qty_unicode=   unicode(int(sheet_obj.cell(rx,3).value))
                    # 判断本次放量数是否为非数字
                    if not ((qty_unicode.encode('utf-8')).strip('-')).isdigit():
                        error_num3 = error_num3+str(rx+1)+','
                        error_flag=1

                    else:
                        # 判断本次放量数是否为0
                        if int(sheet_obj.cell(rx,3).value) == 0:
                            error_num4 = error_num4+str(rx+1)+','
                            error_flag = 1
                        # 判断如果是减量,不能小于可用可交量
                        if int(sheet_obj.cell(rx,3).value) <0:
                            available_qty = self.env['iac.asn.max.qty.create.update'].search([('plant_id','=',plant_id),
                                                                           ('part_id','=',material_id),
                                                                           ('vendor_id','=',vendor_id),
                                                                           ('state','=','done')]).available_qty
                            if int(sheet_obj.cell(rx,3).value)+available_qty<0:
                                error_num5 = error_num5+str(rx+1)+','
                                error_flag = 1


            for item in list(set(show_list)):
                error_num7 = error_num7+'('+item+')'+','
                error_flag=1
            if error_num1 <> '':
                error_str = '第'+error_num1+'行资料错误,在当前Plant下没有该Vendor,请检查！'
            if error_num2<>'':
                error_str = '第'+error_num2+'行资料错误,在当前Plant下没有该Material,请检查！'
            if error_num3<>'':
                error_str = '第'+error_num3+'行资料错误,本次放量数不能为非数字,请检查！'
            if error_num4<>'':
                error_str = '第'+error_num4+'行资料错误,本次放量数不能为0,请检查！'
            if error_num5<>'':
                error_str = '第'+error_num5+'行资料错误,本次减量数不能大于可用可交量,请检查！'
            if error_num6<>'':
                error_str = '第'+error_num6+'行资料错误,comments不能为空,请检查！'
            if error_num7<>'':
                error_str = error_num7+'存在重复资料,请检查！'
            # if error_num8<>'':
            #     error_str = '第'+error_num8+'行资料错误,白名单上的料无需放量,请检查！'

            if error_flag == 0:
                for rx in range(sheet_obj.nrows):
                    if rx >= 1:
                        plant = self.env['pur.org.data'].search(
                            [('plant_code', '=', (sheet_obj.cell(rx, 0).value).strip())])
                        vendor = self.env['iac.vendor.asn'].search(
                            [('vendor_code', '=', (sheet_obj.cell(rx, 1).value).strip())])
                        material = self.env['material.master.asn'].search(
                            [('part_no', '=', (sheet_obj.cell(rx, 2).value).strip()), ('plant_id', '=', plant.id)])

                        result = self.env['asn.maxqty'].search([('plant_id','=',plant.id),
                                                                           ('part_id','=',material.id),
                                                                           ('vendor_id','=',vendor.id),
                                                                           ('state','=','done')])
                        if result:
                            vals = {
                                'increase_qty':int(sheet_obj.cell(rx,3).value),
                                'comments':sheet_obj.cell(rx,4).value,
                                'asn_max_qty_id':result.id
                            }
                            self.env['iac.asn.max.qty.create.line.update'].create(vals)
                            self.env.cr.commit()
                        else:
                            res = self.env['asn.maxqty'].search([('plant_id', '=', plant.id),
                                                                    ('vendor_id', '=', vendor.id),
                                                                    ('part_id', '=', material.id),
                                                                    ('state', '=', 'cancel')], order='id desc', limit=1)
                            if res:
                                engineid = res.engineid
                            else:
                                engineid = 'IACD'

                            self._cr.execute(
                                'insert into asn_maxqty(version,vendorcode,vendor_id,part_id,plant_id,shipped_qty,maxqty,engineid,state,plant,'
                                'material,division,division_id,create_date,write_date,create_uid,write_uid)'
                                'values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                                ('version', (sheet_obj.cell(rx, 1).value).strip(), vendor.id, material.id,
                                 plant.id, 0, 0, engineid, 'done', (sheet_obj.cell(rx, 0).value).strip(),
                                 (sheet_obj.cell(rx, 2).value).strip(),
                                 material.division_id.division, material.division_id.id,
                                 datetime.datetime.now(), datetime.datetime.now(),
                                 self._uid, self._uid))
                            self.env.cr.commit()

                            r = self.env['asn.maxqty'].search([('plant_id', '=', plant.id),
                                                                    ('part_id', '=', material.id),
                                                                    ('vendor_id', '=', vendor.id),
                                                                    ('state', '=', 'done')])
                            vals = {
                                'increase_qty': int(sheet_obj.cell(rx, 3).value),
                                'comments': sheet_obj.cell(rx, 4).value,
                                'asn_max_qty_id': r.id
                            }
                            self.env['iac.asn.max.qty.create.line.update'].create(vals)
                            self.env.cr.commit()


            if error_str<>'':
                raise UserError(error_str)
            else:
                raise UserError('上传成功')

        else:
            raise UserError('模版格式错误,请重新上传！')
# 批量放量程序ning add 190325 end


#批量放量程序废除 begin 190321
class AsnMaxQtyImportWizard(models.TransientModel):
    _name = 'asn.maxqty.import.wizard'
    _inherit = 'iac.file.import'


    @api.multi
    def action_upload_file(self):
        """
        上传文件按钮入口
        :return:
        """
        model_name="asn.maxqty"

        fields = ['plant_id','vendor_id','material','maxqty','comments']
        process_result,import_result,action_url=super(AsnMaxQtyImportWizard,self).import_file(model_name,fields)
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

        ids=import_result["ids"]
        #合并最大可交量
        for asn_max_id in ids:
            asn_max_rec=self.env["asn.maxqty"].browse(asn_max_id)
            domain=[('vendor_id','=',asn_max_rec.vendor_id.id),('part_id','=',asn_max_rec.part_id.id)]
            domain+=[('state','=','done'),('id','<',asn_max_rec.id)]
            last_asn_max_rec=self.env["asn.maxqty"].search(domain,limit=1)
            asn_max_vals={
                "vendorcode":asn_max_rec.vendor_id.vendor_code,
                "engineid":"IACW",
                "plant":asn_max_rec.plant_id.plant_code,
                "state":"done",

            }
            asn_max_rec.write(asn_max_vals)
            if last_asn_max_rec.exists():
                last_asn_max_rec.write({"state":"cancel"})
                asn_max_vals["engineid"]=last_asn_max_rec.engineid
                asn_max_vals["shipped_qty"]=last_asn_max_rec.shipped_qty
                asn_max_vals["maxqty"]=asn_max_rec.maxqty+last_asn_max_rec.shipped_qty
            asn_max_rec.write(asn_max_vals)
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
            pass
            #field_index=import_fields.index("input_price")
            #field_val=data_line[field_index]

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
        file_template=self.env["muk_dms.file"].search([('filename','=','asn_max_qty_import.xls')],limit=1,order='id desc')
        if not file_template.exists():
            raise UserError('File Template with name ( %s ) does not exists!'%("asn_max_qty_import.xls",))
        action = {
            'type': 'ir.actions.act_url',
            'url': '/dms/file/download/%s'%(file_template.id,),
            'target': 'new',
        }
        return action
#批量放量程序废除 end 190321


#190307 放量程序 废除 begin
class IacAsnMaxQtyCreate(models.Model):
    _inherit="asn.maxqty"
    _name="iac.asn.max.qty.create"
    _table="asn_maxqty"
    _order = 'id desc'

    plant_id = fields.Many2one('pur.org.data', string=u'工廠', index=True)
    vendor_id=fields.Many2one("iac.vendor.asn",string=u"廠商")
    part_id_inc = fields.Many2one('material.master.asn', string=u'料號')
    increase_qty =fields.Integer(string=u'待開ASN數量',default=0)
    comments=fields.Text(string="Comments")
    asn_increase_line_ids=fields.One2many('iac.asn.max.qty.create.line','asn_max_qty_id',string='ASN Increase QTY Info')
    maxqty=fields.Integer(string=u'初始最大可交量',default=0)
    shipped_qty =fields.Integer(string=u'已開ASN數量',default=0)
    remained_qty =fields.Integer(string=u'可開ASN數',compute='_compute_remained_qty')
    part_id = fields.Many2one('material.master.asn', string=u'料號',compute = '_compute_fields',store=True)
    file_line_no=fields.Integer(string='File Line No')
    engineid = fields.Selection([("IACD","IACD"),("IACW","IACW")],string="Engineid",default="IACD")
    state=fields.Selection([('cancel','Cancel'),('done','Done')],string='State',default='done')
    last_max_qty_id=fields.Many2one('asn.maxqty',string='Last Max Qty')
    #计算字段
    max_qty_last = fields.Float(string=u'最終可交量',compute='_taken_max_qty_last')# SAP传过来的订单总额

    @api.one
    @api.depends('maxqty', 'shipped_qty')
    def _compute_remained_qty(self):
        inc_qty_sum=0
        for asn_inc_qty in self.asn_increase_line_ids:
            inc_qty_sum+=asn_inc_qty.increase_qty
        self.remained_qty = self.maxqty +inc_qty_sum- self.shipped_qty

    @api.one
    @api.depends('maxqty', 'shipped_qty')
    def _taken_max_qty_last(self):
        inc_qty_sum=0
        for asn_inc_qty in self.asn_increase_line_ids:
            inc_qty_sum+=asn_inc_qty.increase_qty
        self.max_qty_last = self.maxqty +inc_qty_sum

    @api.multi
    def write(self,vals):
        result=super(IacAsnMaxQtyCreate,self).write(vals)
        #当增加数量的情况下,需要重置increase_qty 和comments 字段
        if "increase_qty" in vals:
            for asn_max_id in self.ids:
                asn_max_qty_rec=self.env["iac.asn.max.qty.create"].browse(asn_max_id)
                #创建明细条目记录
                asn_inc_qty_vals={
                    "asn_max_qty_id":asn_max_qty_rec.id,
                    "plant_id":asn_max_qty_rec.plant_id.id,
                    "vendor_id":asn_max_qty_rec.vendor_id.id,
                    "part_id":asn_max_qty_rec.part_id.id,
                    "increase_qty":asn_max_qty_rec.increase_qty,
                    "comments":asn_max_qty_rec.comments
                }
                #获取目标数量比当前数量的差值
                diff_qty=asn_max_qty_rec.increase_qty-asn_max_qty_rec.remained_qty
                asn_inc_qty_vals["increase_qty"]=diff_qty
                asn_inc_qty_rec=self.env["iac.asn.max.qty.create.line"].create(asn_inc_qty_vals)
                super(IacAsnMaxQtyCreate,asn_max_qty_rec).write({"comments":False,"increase_qty":0})

        return result

    @api.model
    def create(self,vals):
        base_vals={}
        base_vals.update(vals)
        base_vals["maxqty"]=vals.get("increase_qty")
        part_rec=self.env["material.master.asn"].browse(vals.get("part_id_inc"))
        base_vals["material"]=part_rec.part_no
        result=super(IacAsnMaxQtyCreate,self).create(base_vals)
        if result.increase_qty<=0:
            raise UserError("Increase Qty must greater than zero")

        #记录创建后补充一些描述字段
        if result.last_max_qty_id.exists():
            #if result.last_max_qty_id.engineid!=result.engineid:
            #    last_engineid=result.last_max_qty_id.engineid
            #    raise UserError("之前有效的 Engineid 为%s,新建记录的Engineid 为%s,不能变更 Engineid" % (last_engineid,result.engineid))
            result.last_max_qty_id.write({"state":"cancel"})
            asn_max_qty_vals={
                "plant_id":result.plant_id.id,
                "plant":result.plant_id.plant_code,
                "division":result.part_id_inc.division,
                "division_id":result.part_id_inc.division_id.id,
                "state":"done",
                "maxqty":result.increase_qty,
                "shipped_qty":result.last_max_qty_id.shipped_qty,
                "increase_qty":0,
                "vendorcode":result.vendor_id.vendor_code,
                "part_id_inc":vals.get("part_id_inc"),
            }
            super(IacAsnMaxQtyCreate,result).write(asn_max_qty_vals)
            #result.write(asn_max_qty_vals)
        else:
            asn_max_qty_vals={
                "plant_id":result.plant_id.id,
                "plant":result.plant_id.plant_code,
                "division":result.part_id_inc.division,
                "division_id":result.part_id_inc.division_id.id,
                "state":"done",
                "engineid":"IACW",
                "maxqty":result.increase_qty,
                "increase_qty":0,
                "vendorcode":result.vendor_id.vendor_code,
                "part_id_inc":vals.get("part_id_inc"),
            }
            super(IacAsnMaxQtyCreate,result).write(asn_max_qty_vals)
        return result

    @api.onchange('vendor_id', 'part_id_inc')
    def onchange_vendor_id_part_id(self):
        if self.plant_id.exists() and self.vendor_id.exists() and self.part_id_inc.exists():
            last_asn_max_rec=self.env["asn.maxqty"].search([('vendor_id','=',self.vendor_id.id),('part_id','=',self.part_id_inc.id),('state','=','done')],order='id desc',limit=1)
            if last_asn_max_rec.exists():
                self.last_max_qty_id=last_asn_max_rec
                self.maxqty=last_asn_max_rec.remained_qty+last_asn_max_rec.shipped_qty
                self.shipped_qty=last_asn_max_rec.shipped_qty


class IacAsnMaxQtyCreateLine(models.Model):
    _name="iac.asn.max.qty.create.line"
    _order = 'id desc'

    plant_id = fields.Many2one('pur.org.data', string='Plant Info')
    vendor_id = fields.Many2one('iac.vendor', string='Vendor Info')
    part_id = fields.Many2one('material.master.asn', string='Part No')
    increase_qty =fields.Integer('Increase QTY',default=0)
    asn_max_qty_id = fields.Many2one('iac.asn.max.qty.create', string='ASN MAX QTY ID')

    comments=fields.Text(string="Comments")

#190307 放量程序 废除 end


#190304 ning调整放量程序
class IacAsnMaxQtyCreateUpdate(models.Model):
    _name = 'iac.asn.max.qty.create.update'
    _inherit = 'asn.maxqty'
    _table = 'asn_maxqty'
    _order = 'part_no'

    plant_id = fields.Many2one('pur.org.data',string='工厂')
    part_id = fields.Many2one('material.master.asn',string='料号')
    part_no = fields.Char(related='part_id.part_no')
    vendor_id = fields.Many2one('iac.vendor.asn',string='厂商')
    engineid = fields.Char(string='Engineid')
    maxqty = fields.Integer(string='FP导入可交量')
    shipped_qty = fields.Integer(string='已开ASN数量')
    available_qty = fields.Integer(string='可用可交量',compute='_get_available_qty')
    change_qty = fields.Integer(string='已放/减量数量(不包含cancel asn产生的增量)',compute='_get_change_qty')
    asn_line_ids = fields.One2many('iac.asn.max.qty.create.line.update', 'asn_max_qty_id',
                                            string='ASN Increase QTY Info')

    @api.one
    @api.depends('shipped_qty')
    def _get_available_qty(self):
        self.available_qty = self.maxqty-self.shipped_qty+self.change_qty



    @api.one
    def _get_change_qty(self):
        # print 1
        # print self.asn_line_ids
        if self.asn_line_ids:
            for item in self.asn_line_ids:
                if not item.asn_line_id:
                    self.change_qty+=item.increase_qty


    @api.multi
    def write(self, vals):
        current_qty = (vals['asn_line_ids'][-1][-1])['increase_qty']
        if self.available_qty+current_qty < 0:
            raise UserError('可交量不能为负数')
        if current_qty == 0:
            raise UserError('本次放量数不能为0')
        result = super(IacAsnMaxQtyCreateUpdate, self).write(vals)

        return result

    @api.onchange('vendor_id', 'part_id')
    def onchange_vendor_id_part_id(self):
        if self.plant_id.exists() and self.vendor_id.exists() and self.part_id.exists():
            last_asn_max_rec=self.env["asn.maxqty"].search([('vendor_id','=',self.vendor_id.id),('part_id','=',self.part_id.id),('state','=','done')],order='id desc',limit=1)
            if last_asn_max_rec.exists():
                # self.last_max_qty_id=last_asn_max_rec
                self.engineid = last_asn_max_rec.engineid
                self.maxqty=last_asn_max_rec.maxqty
                self.shipped_qty=last_asn_max_rec.shipped_qty
                self.available_qty = self.maxqty - self.shipped_qty + self.change_qty

#190305 ning add 放量模型关联表
class IacAsnMaxQtyCreateLineUpdate(models.Model):
    _name="iac.asn.max.qty.create.line.update"
    _order = 'id desc'


    increase_qty =fields.Integer('正数代表放量,负数代表减量',default=0)
    asn_max_qty_id = fields.Many2one('iac.asn.max.qty.create.update', string='ASN MAX QTY ID',readonly=1)
    comments=fields.Text(string="Comments")
    asn_line_id = fields.Many2one('iac.asn.line')


class IacAsnMaxQtyCreateUpdateWizard(models.TransientModel):

    _name = 'iac.asn.max.qty.create.update.wizard'

    plant_id = fields.Many2one('pur.org.data',string='Plant')
    vendor_id = fields.Many2one('iac.vendor.asn',string='Vendor')
    part_id = fields.Many2one('material.master.asn',string='Material')

    @api.onchange('plant_id')
    def _onchange_plant_id_part_id(self):
        self.part_id = False
        if self.plant_id:
            return {'domain':{'part_id':[('plant_id','=',self.plant_id.id)]}}

    #获取代用料
    @api.multi
    def get_alt_grp(self,material_id,plant_id):
        self._cr.execute('select max(fpversion) from iac_traw_data')
        for item in self.env.cr.dictfetchall():
            max_fpversion = item['max']
        res = []
        alt_grp = self.env['iac.traw.data'].search([('material_id','=',material_id),('plant_id','=',plant_id),('fpversion','=',max_fpversion)],limit=1).alt_grp
        if not alt_grp:
            return res
        else:
            traw_data_group = self.env['iac.traw.data'].search([('plant_id','=',plant_id),('alt_grp','=',alt_grp),('fpversion','=',max_fpversion)])

            for traw in traw_data_group:
                max_asn = self.env['asn.maxqty'].search([('plant_id','=',plant_id),('part_id','=',traw.material_id.id),('state','=','done')])
                for max in max_asn:
                    res.append(max.id)
            return res


    @api.multi
    def create_asn_max_qty(self):
        # 轉資料的job正在執行,就不能執行程式20190419 ning add ___begin
        self._cr.execute("  select count(*) as job_count  from ep_temp_master.extractlog "
                         "  where extractname in ( select extractname from ep_temp_master.extractgroup "
                         "                                        where extractgroup = 'ASN' ) "
                         "      and extractstatus = 'ODOO_PROCESS'   ")
        for job in self.env.cr.dictfetchall():
            if job['job_count'] and job['job_count'] > 0:
                raise UserError(' 正在轉資料 ,請勿操作 ! ')
                # 轉資料的job正在執行,就不能執行程式20190419 ning add ___end
        for wizard in self:
            try:
                flag, max_qty, max_qty_id = self.env["asn.jitrule"].kakong(wizard.vendor_id.id, wizard.part_id.buyer_code_id.id,wizard.part_id.id, wizard.vendor_id.vendor_code, wizard.part_id.part_no,wizard.plant_id.id)
            except:
                flag = True
            # if flag == False:
            #     raise UserError('白名单上的料无需放量！')

            re = self.env['asn.maxqty'].search([('plant_id', '=', wizard.plant_id.id),
                                                 ('vendor_id', '=', wizard.vendor_id.id),
                                                 ('part_id', '=', wizard.part_id.id),
                                                 ('state', '=', 'done')])
            if re:
                raise UserError('存在可交量,无法创建')
            else:
                result = self.env['asn.maxqty'].search([('plant_id','=',wizard.plant_id.id),
                                                        ('vendor_id','=',wizard.vendor_id.id),
                                                        ('part_id','=',wizard.part_id.id),
                                                        ('state','=','cancel')],order='id desc',limit=1)
                if result:
                    engineid = result.engineid
                else:
                    engineid = 'IACD'

                self._cr.execute('insert into asn_maxqty(version,vendorcode,vendor_id,part_id,plant_id,shipped_qty,maxqty,engineid,state,plant,'
                                 'material,division,division_id,create_date,write_date,create_uid,write_uid)'
                                 'values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',('version',wizard.vendor_id.vendor_code,wizard.vendor_id.id,wizard.part_id.id,
                                                                 wizard.plant_id.id,0,0,engineid,'done',wizard.plant_id.plant_code,wizard.part_id.part_no,
                                                                 wizard.part_id.division_id.division,wizard.part_id.division_id.id,datetime.datetime.now(),datetime.datetime.now(),
                                                                                         self._uid,self._uid))
                self.env.cr.commit()
                res = self.env['asn.maxqty'].search([('plant_id', '=', wizard.plant_id.id),
                                                        ('vendor_id', '=', wizard.vendor_id.id),
                                                        ('part_id', '=', wizard.part_id.id),
                                                        ('state', '=', 'done')])
                res_list = self.get_alt_grp(wizard.part_id.id,wizard.plant_id.id)
                res_list.append(res.id)
                res_final = list(set(res_list))
        action = {
            'domain': [('id', 'in', res_final)],
            'name': _('ASN Max Qty'),
            'type': 'ir.actions.act_window',
            # 'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.asn.max.qty.create.update'
        }
        return action


    @api.multi
    def search_asn_max_qty(self):
        # 轉資料的job正在執行,就不能執行程式20190419 ning add ___begin
        self._cr.execute("  select count(*) as job_count  from ep_temp_master.extractlog "
                         "  where extractname in ( select extractname from ep_temp_master.extractgroup "
                         "                                        where extractgroup = 'ASN' ) "
                         "      and extractstatus = 'ODOO_PROCESS'   ")
        for job in self.env.cr.dictfetchall():
            if job['job_count'] and job['job_count'] > 0:
                raise UserError(' 正在轉資料 ,請勿操作 ! ')
                # 轉資料的job正在執行,就不能執行程式20190419 ning add ___end
        domain = [('state','=','done')]
        for wizard in self:
            try:
                flag, max_qty, max_qty_id = self.env["asn.jitrule"].kakong(wizard.vendor_id.id, wizard.part_id.buyer_code_id.id,wizard.part_id.id, wizard.vendor_id.vendor_code, wizard.part_id.part_no,wizard.plant_id.id)
            except:
                flag = True
            # if flag == False:
            #     raise UserError('白名单上的料无需放量！')
            if wizard.plant_id:
                domain+=[('plant_id','=',wizard.plant_id.id)]
            if wizard.vendor_id:
                domain+=[('vendor_id','=',wizard.vendor_id.id)]
            if wizard.part_id:
                domain +=[('part_id','=',wizard.part_id.id)]

            result = self.env['asn.maxqty'].search(domain)
            if not result:
                raise UserError('查无资料,请点击create按钮创建可交量信息')
            else:
                # print result
                res = self.get_alt_grp(result.part_id.id,result.plant_id.id)
                res.append(result.id)
                res_final = list(set(res))


        action = {
            'domain': [('id', 'in', res_final)],
            'name': _('ASN Max Qty'),
            'type': 'ir.actions.act_window',
            # 'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.asn.max.qty.create.update'
        }
        return action