# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _
from datetime import datetime, timedelta
import utility
import logging
from odoo.exceptions import UserError
import  traceback
from odoo.odoo_env import odoo_env
from vendor_evaluation import IacScorePartCategory
_logger = logging.getLogger(__name__)

# 定时任务，生成供应商评鉴数据
class TaskVendorScore(models.Model):
    """
    计算分数思路：1.生成待评核名单
                  2.通过分组统计SC CODE,Plant,part_category的入料数量和金额
                  3.计算SC CODE,Plant,part_category在iac.score.definition表中定义的评分项得分
    #  20181204 laura modify : A33文件的Active 日期 改抓 iac_vendor_attachment 的 upload_date
    """


    _name = 'task.vendor.score'

    name = fields.Char(string="Name")

    @odoo_env
    def cron_vendor_scoring(self):
        _logger.warn(u'定时任务启动，开始生成供应商评鉴数据...')

        score_snapshot = fields.Date.today()  # 快照号
        try:
            # 自动产生评核名单
            domain = []
            print '***30:  start-gen_score_list '
            score_list = self.gen_score_list(score_snapshot,domain,'job')
            print '***31:  end -gen_score_list : ',score_list
            _logger.debug(u'评核名单生成操作完成...')

            # 1.备份评分标准资料
            if score_list:
                self.backup_score_data(score_snapshot)
            _logger.warn(u'评分标准资料备份完成...')

            # 计算分值，每个supplier_company、plant调用一次计算方法
            for score_list_id in score_list:
                self.calc_vendor_score(score_list_id,score_snapshot,'job')
                _logger.warn("supplier company %s 计算分值完成"%(score_list_id.supplier_company_id.company_no))
            _logger.warn(u'分值计算完成...')


            #建立模型关联
            self.create_class_part_data(score_snapshot)
            #建立模型关联
            self.create_class_company_data(score_snapshot)

            self.cal_sc_class_score(score_list,score_snapshot)
            # supplier_company_id_list = []
            # for score_list_id in score_list:
            #     supplier_company_id_list.append(score_list_id.supplier_company_id.id)
            #     supplier_company_id_list = list(set(supplier_company_id_list))
            # for supplier_company_id in supplier_company_id_list:
            #     class_sc = self.env['iac.class.supplier_company'].search([('supplier_company_id','=',supplier_company_id),('score_snapshot','=',score_snapshot)])
            #     # 190925 ning add 更新class sc的等级和分数
            #     class_sc.cal_class_supplier_company()
            #     for class_part_category in self.env['iac.class.part_category'].search([('class_supplier_company_id','=',class_sc.id),('score_snapshot','=',score_snapshot)]):
            #         # 190925 ning add 更新class part category的分数和等级
            #         class_part_category.cal_class_part_category()



            #更新supplier_company 层次的数据
            #self.update_supplier_company_score(score_list,score_snapshot)
            _logger.warn(u'更新分值数据完成...')
            #计算风险等级
            score_list_ids=[]
            for score_list_id in score_list:
                score_list_ids.append(score_list_id.id)
            self.calcu_supplier_company_risk(score_list_ids,score_snapshot)
            _logger.warn(u'风险等级数据生成完成...')
            #写入log表
            score_list_ids = []
            for score_list_id in score_list:
                score_list_ids.append(score_list_id.id)
            self.insert_score_approve_log(score_list_ids,score_snapshot,'system','initial','系统初始化评分数据')
            self.insert_class_approve_log(score_list_ids,score_snapshot,'system','产生评鉴资料','系统初始化评分数据')
            _logger.warn(u'log表写入完成...')
            _logger.warn(u'供应商评鉴数据生成完成...')
        except:
            traceback.print_exc()
            err_msg="计算供应商评鉴数据发生异常\n %s"%(traceback.format_exc(),)
            _logger.error("计算供应商评鉴数据发生异常\n %s"%(traceback.format_exc(),))
            raise Exception(err_msg)

        return True


    #ning add 更新class sc以及class part category的等级和分数
    def cal_sc_class_score(self,score_list,score_snapshot):
        supplier_company_id_list = []
        for score_list_id in score_list:
            supplier_company_id_list.append(score_list_id.supplier_company_id.id)
        supplier_company_id_list = list(set(supplier_company_id_list))
        for supplier_company_id in supplier_company_id_list:
            class_sc = self.env['iac.class.supplier_company'].search(
                [('supplier_company_id', '=', supplier_company_id), ('score_snapshot', '=', score_snapshot)])
            # 190925 ning add 更新class sc的等级和分数
            class_sc.cal_class_supplier_company()
            for class_part_category in self.env['iac.class.part_category'].search(
                    [('class_supplier_company_id', '=', class_sc.id), ('score_snapshot', '=', score_snapshot)]):
                # 190925 ning add 更新class part category的分数和等级
                class_part_category.cal_class_part_category()

    #ning add 写入log表的方法
    def insert_score_approve_log(self,score_list_ids,score_snapshot,approve_role,approve_status,memo):
        #向iac_score_approve_log表中写入资料
        for score_list_id in score_list_ids:
            score_part_category_objs = self.env['iac.score.part_category.inherit'].sudo().search([('score_snapshot','=',score_snapshot),('score_list_id','=',score_list_id)])
            for score_part_category in score_part_category_objs:
                score_approve_vals = {
                    'score_snapshot':score_snapshot,
                    'score_part_category_id':score_part_category.id,
                    'user_id':self._uid,
                    'approve_role':approve_role,
                    'approve_status':approve_status,
                    'memo':memo,
                    'part_category_id':score_part_category.part_category_id.id,
                    'user_score': score_part_category.user_score
                }
                self.env['iac.score.approve.log'].create(score_approve_vals)
    def insert_class_approve_log(self,score_list_ids,score_snapshot,approve_role,action,memo):
        #向iac_class_approve_log表中写入资料
        supplier_company_list = []
        for score_list_id in score_list_ids:
            score_list_obj = self.env['iac.score.list'].browse(score_list_id)
            supplier_company_list.append(score_list_obj.supplier_company_id.id)
        supplier_company_list = list(set(supplier_company_list))
        for supplier_company_id in supplier_company_list:
            class_supplier_company_obj = self.env['iac.class.supplier_company'].search([('score_snapshot','=',score_snapshot),('supplier_company_id','=',supplier_company_id)])
            class_approve_vals = {
                'score_snapshot':score_snapshot,
                'class_supplier_company_id':class_supplier_company_obj.id,
                'user_id':self._uid,
                'approve_role':approve_role,
                'action':action,
                'memo':memo,
                'user_class': class_supplier_company_obj.user_class
            }
            self.env['iac.class.approve.log'].create(class_approve_vals)

    def update_supplier_company_score(self, score_list, score_snapshot):
        """
        更新当前的supplier_company 的score
        :param score_list:
        :param score_snapshot:
        :return:
        """
        #获取supplier_company_id 列表
        supplier_company_id_list=[]
        for score_list_rec in score_list:
            supplier_company_id_list.append(score_list_rec.supplier_company_id.id)
        supplier_company_id_list=list(set(supplier_company_id_list))

        #每个supplier_company 更新下权重相关数据
        #更新part_category 的权重数据
        for supplier_company_id in  supplier_company_id_list:
            sc_rec=self.env["iac.supplier.company"].browse(supplier_company_id)
            sc_rec.update_score_weight(score_snapshot)
            domain=[('supplier_company_id','=',supplier_company_id)]
            domain+=[('score_snapshot','=',score_snapshot)]
            score_part_category_list=self.env["iac.score.part_category"].sudo().search(domain)
            for score_part_category in score_part_category_list:
                score_part_category._update_part_category_score_data()



    def calcu_supplier_company_risk(self, score_list_ids, score_snapshot):
        """
        计算评核名单中所有supplier_company的风险等级
        :param score_list:
        :param score_snapshot:
        :return:
        """
        #获取supplier_company_id 列表
        supplier_company_id_list=[]
        for score_list_id in score_list_ids:
            score_list_rec=self.env["iac.score.list"].browse(score_list_id)
            supplier_company_id_list.append(score_list_rec.supplier_company_id.id)
        supplier_company_id_list=list(set(supplier_company_id_list))

        #每个supplier_company 更新下权重相关数据
        #更新part_category 的权重数据
        for supplier_company_id in  supplier_company_id_list:
            sc_rec=self.env["iac.supplier.company"].browse(supplier_company_id)
            vendor_id_list=[]
            vendor_reg_id_list=[]
            for sc_line_rec in sc_rec.line_ids:
                vendor_id_list.append(str(sc_line_rec.vendor_id.id))
                vendor_reg_id_list.append(str(sc_line_rec.vendor_id.vendor_reg_id.id))

            sc_risk_vals={
                "supplier_company_id":supplier_company_id,
                "supplier_company_code":sc_rec.company_no,
                "supplier_company_name":sc_rec.name,
                "state":"submit",
                "score_snapshot":score_snapshot
            }
            if len(vendor_id_list)==0 and len(vendor_reg_id_list)==0:
                continue
            vendor_id_str=','.join(vendor_id_list)
            vendor_reg_id_str=','.join((vendor_reg_id_list))
            str_sql="""
            SELECT
                SUM (iaa.file_count) file_count
            FROM
                (
                    SELECT
                        COUNT (*) file_count
                    FROM
                        iac_vendor_attachment ia
                    WHERE
                        ia.vendor_id IN (%s)
                    AND ia. STATE = 'active'
                    AND ia.memo IS NULL
                    AND ia.file_id IS NOT NULL
                    AND EXISTS (
                        SELECT
                            1
                        FROM
                            iac_attachment_type iat
                        WHERE
                            iat. NAME IN ('A14', 'A32')
                        AND iat. ID = ia.type
                    )
                    UNION ALL
                        SELECT
                            COUNT (*)
                        FROM
                            iac_vendor_register_attachment ira
                        WHERE
                            ira.vendor_reg_id IN (%s)
                        AND ira. STATE = 'active'
                        AND ira.memo IS NULL
                        AND ira.file_id IS NOT NULL
                        AND EXISTS (
                            SELECT
                                1
                            FROM
                                iac_attachment_type iat
                            WHERE
                                iat. NAME IN ('A14', 'A32')
                            AND iat. ID = ira.type
                        )
                ) iaa            """%(vendor_id_str,vendor_reg_id_str)
            #判断风险等级是否为低
            self.env.cr.execute(str_sql)

            #判断风险等级是否为低
            pg_result = self.env.cr.dictfetchone()
            if pg_result["file_count"]>0:
                sc_risk_vals["calculate_level"]="low"
                sc_risk_vals["user_level"]="low"
                self.env["iac.supplier.company.risk"].create(sc_risk_vals)
                continue

            #判断风险等级是否为中
            str_sql="""
            SELECT
                SUM (iaa.file_count) file_count
            FROM
                (
                    SELECT
                        COUNT (*) file_count
                    FROM
                        iac_vendor_attachment ia
                    WHERE
                        ia.vendor_id IN (%s)
                    AND ia. STATE = 'active'
                    AND ia.memo IS not NULL
                    AND ia.file_id IS NOT NULL
                    AND EXISTS (
                        SELECT
                            1
                        FROM
                            iac_attachment_type iat
                        WHERE
                            iat. NAME IN ('A14', 'A32')
                        AND iat. ID = ia.type
                    )
                    UNION ALL
                        SELECT
                            COUNT (*)
                        FROM
                            iac_vendor_register_attachment ira
                        WHERE
                            ira.vendor_reg_id IN (%s)
                        AND ira. STATE = 'active'
                        AND ira.memo IS not NULL
                        AND ira.file_id IS NOT NULL
                        AND EXISTS (
                            SELECT
                                1
                            FROM
                                iac_attachment_type iat
                            WHERE
                                iat. NAME IN ('A14', 'A32')
                            AND iat. ID = ira.type
                        )
                ) iaa            """%(vendor_id_str,vendor_reg_id_str)
            self.env.cr.execute(str_sql)
            pg_result = self.env.cr.dictfetchone()
            if pg_result["file_count"]>0:
                sc_risk_vals["calculate_level"]="medium"
                sc_risk_vals["user_level"]="medium"
                self.env["iac.supplier.company.risk"].create(sc_risk_vals)
                continue

            #判断风险等级是否为高
            str_sql="""
            SELECT
                SUM (iaa.file_count) file_count
            FROM
                (
                    SELECT
                        COUNT (*) file_count
                    FROM
                        iac_vendor_attachment ia
                    WHERE
                        ia.vendor_id IN (%s)
                    AND ia. STATE = 'active'
                    AND ia.file_id IS NOT NULL
                    AND EXISTS (
                        SELECT
                            1
                        FROM
                            iac_attachment_type iat
                        WHERE
                            iat. NAME IN ('A14', 'A32')
                        AND iat. ID = ia.type
                    )
                    UNION ALL
                        SELECT
                            COUNT (*)
                        FROM
                            iac_vendor_register_attachment ira
                        WHERE
                            ira.vendor_reg_id IN (%s)
                        AND ira. STATE = 'active'
                        AND ira.file_id IS NOT NULL
                        AND EXISTS (
                            SELECT
                                1
                            FROM
                                iac_attachment_type iat
                            WHERE
                                iat. NAME IN ('A14', 'A32')
                            AND iat. ID = ira.type
                        )
                ) iaa            """%(vendor_id_str,vendor_reg_id_str)

            self.env.cr.execute(str_sql)
            pg_result = self.env.cr.dictfetchone()
            if pg_result["file_count"]==0:
                sc_risk_vals["calculate_level"]="high"
                sc_risk_vals["user_level"]="high"
                self.env["iac.supplier.company.risk"].create(sc_risk_vals)
                continue

    #190918 ning 调整产生评核名单的方法 增加参数score_type 判断产生评核名单的方式
    def gen_score_list(self,score_snapshot,domain,score_type):
        """
        产生评核名单
        :return:
        """
        score_list = []
        if score_type == 'job':

            # 2.抓取可以評核的廠商列表

            domain += [('company_no', '!=', ''), ('current_class', 'not in', ['D', 'DW'])
                       #,('id', 'in', ['3486', '3484']) # laura test 20180831 只抓前面10筆資料
                        #,('id','in','()'),('id','<=','3500')  # laura test 20180831 只抓前面10筆資料
                       ]
            sc_list = self.env['iac.supplier.company'].search_read(
                domain, ['id', 'create_date', 'current_class', 'class_date'])
                #, order='id desc', limit=400   # laura test 20181011
            print '***296:',sc_list
            sc_remove_list = [] # 要remove的sc
            # 排除不参与评核的supplier
            scoring_list = []  # 评核中的sc
            for item in self.env['iac.score.list'].search([('state', '=', 'scoring')]):
                # print '***299:', item
                scoring_list.append(item.supplier_company_id.id)
                # print '***301:', item.supplier_company_id.id
            approving_part_category = []  # 材料类别评分未确认的sc
            for item in self.env['iac.score.part_category'].search([('create_date','>','2019-10-10'),'|',('qm_state', '!=', 'done'),('scm_state','!=','done')]):
                # print '***304:', item
                approving_part_category.append(item.supplier_company_id.id)
                # print '***306:', item.supplier_company_id.id
            exclude_supplier = []  # 排除的sc
            for item in self.env['iac.score.exclude'].search([('active', '=', True)]):
                #print '***309:', item
                exclude_supplier.append(item.supplier_company_id.id)
                #print '***311:', item.supplier_company_id.id
            sc_gr_list = []# 保存SC在plant下有GR的数据
            for sc in sc_list:
                # 防止class_date为空
                if sc['class_date']:
                    class_date = sc['class_date']
                else:
                    class_date = sc['create_date']

                if sc['id'] in scoring_list:
                    print '***323:',scoring_list
                    sc_remove_list.append(sc['id'])
                    continue
                if sc['id'] in approving_part_category:
                    print '***327:', approving_part_category
                    sc_remove_list.append(sc['id'])
                    continue
                if sc['id'] in exclude_supplier:
                    print '***331:', exclude_supplier
                    sc_remove_list.append(sc['id'])
                    continue
                if sc['id'] in exclude_supplier:
                    print '***335:', exclude_supplier
                    sc_remove_list.append(sc['id'])
                    continue
                # 3.新建的SupplierCompany code，存在90天以上的可以參與第一次評核，否則不評
                deadline = datetime.today() - timedelta(days=90)
                if fields.Datetime.from_string(sc['create_date']) > deadline:
                    sc_remove_list.append(sc['id'])

                # 4.已經評核過的廠商，按照材料大類評核等級，SC評核等級，Vendor code評核等級的優先順序，找到一筆即停，比對上次評核的等級與規定天數，決定本次是否免評核。
                deadline_365 = datetime.today() - timedelta(days=365)
                deadline_180 = datetime.today() - timedelta(days=180)
                deadline_90 = datetime.today() - timedelta(days=90)

                if sc['current_class'] == 'A' and fields.Datetime.from_string(class_date) > deadline_365:
                    sc_remove_list.append(sc['id'])
                if sc['current_class'] == 'B' and fields.Datetime.from_string(class_date) > deadline_180:
                    sc_remove_list.append(sc['id'])
                if sc['current_class'] in ['C', 'D', 'DW'] and fields.Datetime.from_string(class_date) > deadline_90:
                    sc_remove_list.append(sc['id'])

                # A/B/C級 SC 從上次評核 到今天這段期間  有沒有GR  如果沒有GR要踢掉 by Jocelyn
                if sc['current_class'] in ['A', 'B', 'C']:
                    # 查询SC在plant下的GR，如果SC的某个vendor没有GR将被排除
                    gr_sql_query = """select v.supplier_company_id, v.plant, sum(gr.qty_received)
                                        from goods_receipts gr, iac_vendor v
                                        where gr.vendor_id = v.id
                                        and gr.qty_received > 0
                                        and v.state = 'done'
                                        and v.supplier_company_id = %s
                                        and gr.gr_document_date >= %s
                                        group by v.supplier_company_id, v.plant"""

                    params = (sc['id'], class_date)
                    self.env.cr.execute(gr_sql_query, params)
                    for gr in self.env.cr.dictfetchall():
                        # 排除by SC 和Plant设定不评的资料   190910 ning 调整
                        sc_exclude = self.env['iac.score.exclude.plant'].search(
                            [('active', '=', True), ('plant_id', '=', gr['plant']),
                             ('supplier_company_id', '=', gr['supplier_company_id'])])
                        if not sc_exclude:
                            sc_gr_list.append(gr)
                        # sc_exclude = self.env['iac.score.exclude.plant'].search(
                        #     [('active', '=', True), ('plant_id', '=', gr['plant']),
                        #      ('supplier_company_id', '=', gr['supplier_company_id'])])
                        # if sc_exclude:
                        #     continue
                        # if gr['plant'] == 41 and gr['storage_location'] == 'SW01':
                        #     continue
                        # else:
                        #     gr['storage_location'] = ''
                        #     gr['sum'] = ''
                        #     if gr not in sc_gr_list:
                        #         sc_gr_list.append(gr)
                        # IF PLANT = TP02 & SLOC  SW01
                        #     REMOVE
                        # ELSE.
                        #     SLOC = ''
                        #  ENDIF.
                else:
                    sc_remove_list.append(sc['id'])# D/DW的直接排除

            supplier_company_list = []# 符合条件的sc
            for sc in sc_list:
                if sc['id'] not in sc_remove_list:
                    supplier_company_list.append(sc)
            # 根据排除过的supplier company保存评核名单，每个有GR的plant生成一条supplier
            for sc in supplier_company_list:
                print '***380:',sc
                for sc_gr in sc_gr_list:
                    if sc['id'] == sc_gr['supplier_company_id']:
                        supplier = self.env['iac.supplier.company'].browse(sc['id'])
                        print '***384:', supplier
                        vendor_codes = []
                        vendor_ids = []
                        for line_vendor in supplier.line_ids:
                            if line_vendor.vendor_id.plant.id == sc_gr['plant']:
                                vendor_codes.append(line_vendor.vendor_id.vendor_code)
                                vendor_ids.append(line_vendor.vendor_id.id)
                        list_vals = {
                            'supplier_company_id': supplier.id,
                            'plant_id': sc_gr['plant'],
                            'vendor_ids': [(6, 0, vendor_ids)],
                            'score_snapshot': score_snapshot
                        }
                        print '***397:',list_vals
                        score_list.append(self.env['iac.score.list'].create(list_vals))  # 生成评核名单
        else:
            # sc_gr_list = []
            sc_obj = self.env['iac.supplier.company'].search(domain)
            if self.env['iac.score.list'].search([('state','=','scoring'),('supplier_company_id','=',sc_obj.id)]):
                raise UserError('当前supplier company评核未完成')
            if self.env['iac.score.part_category'].search([('supplier_company_id','=',sc_obj.id),
                                                           ('create_date','>','2019-10-10'),'|',('qm_state', '!=', 'done'),('scm_state','!=','done')]):
                raise UserError('当前supplier company存在未确认的材料大类评鉴')

            self.env.cr.execute("""
                    select DISTINCT(company_no) from iac_supplier_company isc 
                INNER JOIN iac_supplier_company_line iscl on isc.id = iscl.supplier_company_id and iscl.vendor_id not in
                 (select DISTINCT(vendor_id) from goods_receipts where gr_document_date>='2000-01-01' and vendor_id is not null)
                where company_no=%s
                        """,(sc_obj.company_no,))
            gr_result = self.env.cr.dictfetchone()
            if gr_result:
                raise UserError("自2000年起到现在未发生过入料的Supplier company，无法确认"
                                "评鉴的part category，请联系IT PM")

            # # 查询SC在plant下的GR，如果SC的某个vendor没有GR将被排除
            # gr_sql_query = """select v.supplier_company_id, v.plant, sum(gr.qty_received)
            #                             from goods_receipts gr, iac_vendor v
            #                             where gr.vendor_id = v.id
            #                             and gr.qty_received > 0
            #                             and v.state = 'done'
            #                             and v.supplier_company_id = %s
            #                             and gr.gr_document_date >= %s
            #                             group by v.supplier_company_id, v.plant"""
            #
            # params = (sc_obj.id, class_date)
            # self.env.cr.execute(gr_sql_query, params)
            # sc_objs = self.env.cr.dictfetchall()
            # if not sc_objs:
            #     raise UserError('当前supplier company上一次评核至今未入过料')
            # else:
            #     for gr in sc_objs:
            #         sc_gr_list.append(gr)


            # for sc_gr in sc_gr_list:
            #     if sc_obj.id == sc_gr['supplier_company_id']:
            #         supplier = self.env['iac.supplier.company'].browse(sc_obj.id)
            #         print '***384:', supplier

            plant_ids = []
            for line_vendor in sc_obj.line_ids:
                if line_vendor.vendor_id.state in ('done','deleted','block'):
                    plant_ids.append(line_vendor.vendor_id.plant.id)
            plant_ids = list(set(plant_ids))
            #抓该sc最大的gr时间
            self.env.cr.execute("""
                        select max(gr_document_date) from goods_receipts where vendor_id in (
                select vendor_id from iac_supplier_company_line where supplier_company_id=%s)
                    """,(sc_obj.id,))
            gr_date_result = self.env.cr.dictfetchone()
            if sc_obj.current_class == 'A':
                gr_begin_date = datetime.strptime(gr_date_result['max'],'%Y-%m-%d')-timedelta(days=365)
            elif sc_obj.current_class == 'B':
                gr_begin_date = datetime.strptime(gr_date_result['max'],'%Y-%m-%d') - timedelta(days=180)
                # gr_begin_date = gr_date_result['max'] - timedelta(days=180)
            else:
                gr_begin_date = datetime.strptime(gr_date_result['max'],'%Y-%m-%d') - timedelta(days=90)

            for plant_id in plant_ids:
                vendor_codes = []
                vendor_ids = []
                for line_vendor in sc_obj.line_ids:
                    if plant_id == line_vendor.vendor_id.plant.id:
                        self.env.cr.execute("""
                                        select * from goods_receipts where vendor_id=%s and 
                                        plant_id = %s and gr_document_date>=%s
                                    """,(line_vendor.vendor_id.id,plant_id,gr_begin_date))
                        vendor_gr_result = self.env.cr.dictfetchall()
                        if vendor_gr_result:
                            vendor_codes.append(line_vendor.vendor_id.vendor_code)
                            vendor_ids.append(line_vendor.vendor_id.id)
                if len(vendor_ids)>0:
                    list_vals = {
                        'supplier_company_id': sc_obj.id,
                        'plant_id': plant_id,
                        'vendor_ids': [(6, 0, vendor_ids)],
                        'score_snapshot': score_snapshot
                    }
                    print '***397:',list_vals
                    score_list.append(self.env['iac.score.list'].create(list_vals))  # 生成评核名单

        return score_list

    def backup_score_data(self, score_snapshot):
        """
        备份评分标准资料
        :param score_snapshot:
        :return:
        """

        # 备份前先检查该score_snapshot是否备份过
        records_count = self.env['iac.part_category.material_group.history'].sudo().search_count([('score_snapshot', '=', score_snapshot)])
        if records_count == 0:
            part_category_ids = self.env['iac.part.category'].sudo().search([])
            for part_category in part_category_ids:
                for material_group in part_category.material_group_ids:
                    val = {
                        'part_category_id': part_category.id,
                        'material_group_id': material_group.id,
                        'score_snapshot': score_snapshot
                    }
                    self.env['iac.part_category.material_group.history'].sudo().create(val)
            for item in self.env['iac.score.iqc.mprma'].sudo().search([]):
                val = {
                    'part_category_id': item.part_category_id.id,
                    'score_type': item.score_type,
                    'score': item.score,
                    'lower_limit': item.lower_limit,
                    'high_limit': item.high_limit,
                    'score_snapshot': score_snapshot
                }
                self.env['iac.score.iqc.mprma.history'].sudo().create(val)
            # for item in self.env['iac.fail.cost.section'].sudo().search([]):
            #     val = {
            #         'fail_type': item.fail_type,
            #         'score': item.score,
            #         'lower_limit': item.lower_limit,
            #         'high_limit': item.high_limit,
            #         'score_snapshot': score_snapshot
            #     }
            #     self.env['iac.fail.cost.section.history'].sudo().create(val)

    def calc_vendor_score(self,score_list_id,score_snapshot,type):
        """
        功能：计算评分。生成iac.score.sum分数、iac.score.part_category分数和iac.score.supplier_company分数
        :param supplier:
        :param score_snapshot:
        :return:
        """
        vendor_str = ''  # 20180905 laura add
        # 7.把當前系統設定的SCM controller, QM controller, PE controller, QM leader賦值給評核資料
        scm_controller_id = False
        qm_controller_id = False
        qm_leader_id = False
        for user in self.env.ref('oscg_vendor.group_scm_controller').users:
            if score_list_id.plant_id.id in user.partner_id.plant_ids.ids:
                scm_controller_id = user.partner_id.id
                break
        for user in self.env.ref('oscg_vendor.group_qm_controller').users:
            if score_list_id.plant_id.id in user.partner_id.plant_ids.ids:
                qm_controller_id = user.partner_id.id
                break
        for user in self.env.ref('oscg_vendor.group_qm_leader').users:
            if score_list_id.plant_id.id in user.partner_id.plant_ids.ids:
                qm_leader_id = user.partner_id.id
                break

        # 20180905 laura add---s
        # 抓該筆 SC 的 vendor_id & today
        today = datetime.today().strftime("%Y-%m-%d")

        for vendor in score_list_id.vendor_ids:
            if vendor_str:
                print '*472:', str(vendor.id), '。', vendor_str
                vendor_str = vendor_str + ',' + str(vendor.id)
            else:
                print '*475:', str(vendor.id), '。', vendor_str
                vendor_str = str(vendor.id)
        print '*477:', vendor_str
        # 20180905 laura add---e

        # 5.抓出每個SupplierCompany下的各Site之Vendor Code在上一次評核到job執行當天的入料总金額，MVT只看101,102（退）,105,106（退）,金額用GR數量*MAP/Price unit
        gr_sql_query = """select v.supplier_company_id,gr.plant_id,pcmg.part_category_id,
  sum(gr.qty_received) as gr_qty,
  sum(gr.qty_received * pol.price/pol.price_unit * coalesce(ice.to_currency_amount / ice.from_currency_amount, 1)) as gr_amount
  from goods_receipts gr 
       inner join material_master mm on gr.part_id = mm.id 
       inner join iac_vendor v on gr.vendor_id = v.id 
       inner join iac_part_category_material_group_history pcmg on mm.material_group_id = pcmg.material_group_id
       inner join iac_purchase_order_line pol on gr.part_id = pol.part_id
       inner join iac_purchase_order po on po.id = pol.order_id    
       inner join iac_currency_exchange ice on po.currency_id = ice.from_currency_id
  where gr.qty_received > 0
  and v.supplier_company_id = %s
  and v.plant = %s
  and pcmg.score_snapshot = %s
  and ice.state = 'active'
  and gr.movement_type in ('101', '102', '105', '106')
  and gr.gr_document_date >=%s 
  group by v.supplier_company_id, gr.plant_id, pcmg.part_category_id"""
        # 防止class_date为空
        if score_list_id.supplier_company_id.class_date:
            class_date = score_list_id.supplier_company_id.class_date
        else:
            class_date = score_list_id.supplier_company_id.create_date

        #ning add 如果是手动产生评核名单，gr date需要用当前sc最后一次入料日期减去评核周期
        if type == 'manual':
            # 抓该sc最大的gr时间
            self.env.cr.execute("""
                                    select max(gr_document_date) from goods_receipts where vendor_id in (
                            select vendor_id from iac_supplier_company_line where supplier_company_id=%s)
                                """, (score_list_id.supplier_company_id.id,))
            gr_date_result = self.env.cr.dictfetchone()
            if score_list_id.supplier_company_id.current_class == 'A':
                class_date = datetime.strptime(gr_date_result['max'],'%Y-%m-%d') - timedelta(days=365)
            elif score_list_id.supplier_company_id.current_class == 'B':
                class_date = datetime.strptime(gr_date_result['max'],'%Y-%m-%d') - timedelta(days=180)
            else:
                class_date = datetime.strptime(gr_date_result['max'],'%Y-%m-%d') - timedelta(days=90)

        params = (score_list_id.supplier_company_id.id, score_list_id.plant_id.id, score_snapshot, class_date)
        self.env.cr.execute(gr_sql_query, params)
        pg_gr_results = self.env.cr.dictfetchall()

        # 6.讀取每個site當前supplierCompany上一次評核時的SCM user，QM user人員名單，如果上一次的人員還在職，並且角色沒變，則默認他們，否則默認空值
        #作废
        # scm_partner_id = False
        # qm_partner_id = False
        # score_sc = self.env['iac.score.supplier_company'].sudo().search(
        #     [('score_snapshot', '=', score_list_id.supplier_company_id.score_snapshot),
        #      ('supplier_company_id', '=', score_list_id.supplier_company_id.id)], limit=1)
        # if score_sc:
        #     scm_partner_ids = []
        #     for user in self.env.ref('oscg_vendor.group_scm_user').users:
        #         scm_partner_ids.append(user.partner_id.id)
        #     #if score_sc.scm_partner_id.active and score_sc.scm_partner_id in scm_partner_ids:
        #     #    scm_partner_id = score_sc.scm_partner_id
        #     qm_partner_ids = []
        #     for user in self.env.ref('oscg_vendor.group_qm_user').users:
        #         qm_partner_ids.append(user.partner_id.id)
        #     #if score_sc.qm_partner_id.active and score_sc.qm_partner_id in qm_partner_ids:
        #     #    qm_partner_id = score_sc.qm_partner_id

        score_part_category_ids = []
        for pg_gr_row in pg_gr_results:
            gr_amount = pg_gr_row['gr_amount']
            # # 190924 ning add 汇率转换
            # if pg_gr_row['currency'] == 'USD':
            #     gr_amount = pg_gr_row['gr_amount']
            # else:
            #     rate_query = """
            #                SELECT
            #                   (ice.to_currency_amount/ice.from_currency_amount) as rate
            #                      from iac_currency_exchange ice
            #                   INNER JOIN res_currency rc on ice.from_currency_id = rc.id
            #                     where state='active' and rc.name=%s
            #                      """
            #     params = (pg_gr_row['currency'],)
            #     self.env.cr.execute(rate_query,params)
            #     rate_result = self.env.cr.dictfetchone()
            #     if rate_result:
            #         # 汇率
            #         rate = rate_result['rate']
            #         gr_amount = pg_gr_row['gr_amount']*rate
            # 8.根據IQC AIP系統的資料計算上一次評核結束到目前為止的gr_mappm，gr_mippm，return_mappm，return_mippm，hardness_cost，lrr, tc_qty,等IQC指標
            iqc_sql_query = """select v.supplier_company_id,vsf.plant_id,pcmg.part_category_id,
                        sum(vsf.lurking_cost) as lurking_cost,sum(vsf.hardness_cost) as hardness_cost,
                        case when sum(vsf.qual_qty) = 0 then 0 else sum(vsf.gr_ma)/sum(vsf.qual_qty)*1000000 end as gr_mappm,
                        case when sum(vsf.qual_qty) = 0 then 0 else sum(vsf.gr_mi)/sum(vsf.qual_qty)*1000000 end as gr_mippm,
                        case when sum(vsf.total_count) = 0 then 0 else round(COALESCE((sum(return_count::numeric)+sum(rework_count::numeric)+sum(special_count::numeric))/sum(total_count::numeric),0.00),4) end as lrr,
                        sum(tc_qty)/sum(gr_qty) as tc_qty,
                        case when sum(mo_cnf_qty) = 0 then 0 else sum(rma_ma)/sum(mo_cnf_qty)*1000000 end as return_mappm,
                        case when sum(mo_cnf_qty) = 0 then 0 else sum(rma_mi)/sum(mo_cnf_qty)*1000000 end as return_mippm,
                        sum(vsf.gr_qty) as gr_qty
                        from vs_webflow_iqc_data vsf, iac_vendor v , iac_part_category_material_group_history pcmg
                        where vsf.vendor_id = v.id
                        and vsf.material_group_id = pcmg.material_group_id
                        and v.supplier_company_id = %s
                        and vsf.plant_id = %s
                        and pcmg.part_category_id = %s
                        and vsf.gr_qty > 0
                        and pcmg.score_snapshot = %s
                        and to_date((vsf.cdt),'yyyymm') >= %s
                        group by v.supplier_company_id, vsf.plant_id, pcmg.part_category_id"""
            # 防止class_date为空
            if score_list_id.supplier_company_id.class_date:
                class_date = score_list_id.supplier_company_id.class_date
            else:
                class_date = score_list_id.supplier_company_id.create_date
            params = (score_list_id.supplier_company_id.id, score_list_id.plant_id.id, pg_gr_row['part_category_id'], score_snapshot, class_date)
            self.env.cr.execute(iqc_sql_query, params)
            pg_iqc_result = self.env.cr.dictfetchone()

            part_category_id = self.env['iac.part.category'].browse(pg_gr_row['part_category_id'])
            # 9.根據當前SC的評核類別，讀取評核設定檔
            definitions = self.env['iac.score.definition'].search([('active', '=', True), ('group_code', 'in', ('SCM', 'QM'))])

            # 10.針對上圖每一項的定義設定評核初始記錄，能默認分數的計算分數
            part_category_line_ids = []

            for definition in definitions:
                # 2.1. 依照 廠商等級算出:評分區間  score_list_id.supplier_company_id.current_class
                #  20180905 laura add---s
                # 評分區間:用job執行日期 - 以下天數 (A級廠商:365天, B級廠商:180, C級廠商:90天)
                if score_list_id.supplier_company_id.current_class == 'A':
                    class_date_end = datetime.today() - timedelta(days=365)  # 今天 -365
                if score_list_id.supplier_company_id.current_class == 'B':
                    class_date_end = datetime.today() - timedelta(days=180)  # 今天 -180
                if score_list_id.supplier_company_id.current_class in ('C','',None):
                    class_date_end = datetime.today() - timedelta(days=90)  # 今天 -90
                if score_list_id.supplier_company_id.current_class in ('D', 'DW'):
                    class_date_end = datetime.today()

                class_date_end = class_date_end.strftime("%Y-%m-%d")
                # 20180905 laura add---e

                # SCM
                # Sequence = 1，價格競爭力 废弃
                # if definition.group_code == 'SCM' and definition.code == 'SCM1' and definition.part_class.id == part_category_id.part_class.id:
                #     score_value = ''
                #     calculate_score = 0
                #     part_category_line_id = {
                #         'vs_def_id': definition.id,
                #         'score_value': score_value,
                #         'calculate_score': calculate_score,
                #         'user_score':calculate_score,
                #         'score_snapshot': score_snapshot,
                #         'supplier_company_id':pg_gr_row["supplier_company_id"],
                #         'score_list_id':score_list_id.id,
                #         'plant_id':score_list_id.plant_id.id,
                #         'part_category_id':pg_gr_row['part_category_id'],
                #     }
                #     part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 2，配合IAC降價 废弃
                # elif definition.group_code == 'SCM' and definition.code == 'SCM2' and definition.part_class.id == part_category_id.part_class.id:
                #     score_value = ''
                #     calculate_score = 0
                #     part_category_line_id = {
                #         'vs_def_id': definition.id,
                #         'score_value': score_value,
                #         'calculate_score': calculate_score,
                #         'user_score':calculate_score,
                #         'score_snapshot': score_snapshot,
                #         'supplier_company_id':pg_gr_row["supplier_company_id"],
                #         'score_list_id':score_list_id.id,
                #         'plant_id':score_list_id.plant_id.id,
                #         'part_category_id':pg_gr_row['part_category_id'],
                #     }
                #     part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 3, Payment term項
                if definition.group_code == 'SCM' and definition.code == 'SCM3' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = ''
                    temp_value = ''
                    calculate_score = 0
                    temp_score = 0
                    # 遍历当前site下SC的正常vendor的payment terms
                    for vendor in score_list_id.vendor_ids:
                        if vendor.state in ('done', 'block'):
                            payment_term_id = vendor.payment_term
                            for score_range in self.env['iac.score.range'].search(
                                    [('log_type', '=', 'VS_P_PAYMENT_TERM')]):
                                if payment_term_id.payment_term == score_range.level_t:
                                    temp_value = payment_term_id.payment_term
                                    temp_score = score_range.score
                                    break
                            if temp_score > calculate_score:
                                score_value = temp_value
                                calculate_score = temp_score
                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))

                # Sequence = 4, 入料配合方式
                # 入料配合方式 laura add 20181005 : 1. Vendor Code 設定為VMI：6分。
                elif definition.group_code == 'SCM' and definition.code == 'SCM4' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = ''
                    calculate_score = 0
                    over_rate = 0   # "超額入料比例"
                    # 4.1. Vendor Code 設定為VMI：6分。  vmi_supplier='yes' >> 6分, 後面就不處理
                    self._cr.execute(" select distinct vendor.vmi_supplier vmi_supplier , pur.plant_code plant_code "
                                     "  from iac_vendor vendor , pur_org_data pur  "
                                     "where vendor.plant = pur.id and vendor.id in (" + vendor_str + ")" )
                    for item in self.env.cr.dictfetchall():
                        print '***650:',item['vmi_supplier'],'。',item['plant_code']
                        vmi_supplier = item['vmi_supplier']
                        plant_code = item['plant_code']

                    print '***654:', vmi_supplier, '。', plant_code

                    if vmi_supplier and vmi_supplier == 'yes' :
                        # 4.1. Vendor Code 設定為VMI：6分。  vmi_supplier='yes' >> 6分, 後面就不處理
                        #190905 ning 调整 6分改8分
                        calculate_score = 8
                    else:
                        if plant_code and plant_code == 'CP22':
                            # 4.3. CP22 沒有導入最大可交量，系統默認 0分。 > 該vendor是CP22的就給0分
                            # 190905 ning 调整 0分改7分
                            calculate_score = 7
                        else:
                            # 190905 ning 调整 6分改8分
                            calculate_score = 8 # "超額入料比例" 預設 6分
                            #190910 ning 调整  只查财务人员的放量记录
                            self._cr.execute(" select  sum(COALESCE(ins.increase_qty,0)) as ins_qty "
                                  "from  asn_maxqty asn ,iac_asn_max_qty_create_line_update ins "
                                 "where ins.asn_max_qty_id = asn.id "
                                     "and ins.increase_qty > 0 "
                                     "and ( ins.create_uid in ( select ru.id from res_groups rp "
                                    "inner join res_groups_users_rel gu on gu.gid = rp.id "
                                    "inner join res_users ru on ru.id = gu.uid "
                                    "where rp.name = 'FRM' and ru.active = 't'  ) ) "
                                     " and asn.vendor_id in  (" + vendor_str + ") ")
                            for ans in self.env.cr.dictfetchall():
                                print '***674:', ans['ins_qty']
                                ins_qty = ans['ins_qty'] # 放量總數
                                if ins_qty :
                                    # 4.2.3.  計算 "總入料數量"
                                    self._cr.execute(
                                        " select sum(qty_total)  as  qty_total from  goods_receipts  "
                                        " where vendor_id in  (" + vendor_str + ")")
                                    for gr in self.env.cr.dictfetchall():
                                        print '***682:', gr['qty_total']
                                        qty_total = gr['qty_total'] # 入料總數
                                    # 4.2.4.  計算 "超額入料比例" = 放量總數量/總入料數量。
                                    if qty_total :
                                        over_rate = ins_qty / qty_total # "超額入料比例"
                                        # 190905 ning 调整 4分改6分
                                        if over_rate < 0.01 :  #超額入料比例 < 10 %   4分
                                            calculate_score = 6
                                        # 190905 ning 调整 3分改5分
                                        elif over_rate >= 0.01 :  #超額入料比例 >= 10 %   3分
                                            calculate_score = 5
                                    else:
                                        # 190905 ning 调整 6分改8分
                                        calculate_score = 8 # 沒有 GR入料數>>超額入料比例=0% 6分
                                else:
                                    # 190905 ning 调整 6分改8分
                                    calculate_score = 8  # 4.2.0. FRM角色 人員都沒有 把asn的最大可交量改大,就給6分,也不用計算 "超額入料比例"

                    print '***696:',over_rate,'。',calculate_score,'。',vmi_supplier,'。',plant_code

                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 5, 交期回復配合度
                # 交期回復配合度 laura add 20180831 : 1. 有導入 EDI830/830R : 6分 ( iac_edi_vendor_list 有值:6分)  2. 在odoo評分區間內有上傳交期  3. 其他:3分
                elif definition.group_code == 'SCM' and definition.code == 'SCM5' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = ''
                    # 190905 ning 调整 3分改5分
                    calculate_score = 5  # 3. 其他3分 (預設3分)

                    supply_list = []  # 符合6分條件的 sc

                    #交期回復配合度 laura add 20180831 ----s
                    # 1. 有導入 EDI830/830R : 6分 ( iac_edi_vendor_list 有值:6分)
                    print '***654 : ', score_list_id.vendor_ids.ids,',',score_list_id.supplier_company_id ,',',score_list_id
                    print '***655 : ', score_list_id.supplier_company_id.class_date,',',score_list_id.supplier_company_id.current_class
                    for edi830 in self.env['iac.edi.vendor.list'].sudo().search(
                            [('vendor_id', 'in', score_list_id.vendor_ids.ids), ('active', '=', '1')]):
                        if edi830.vendor_id.id in score_list_id.vendor_ids.ids:
                            print '***659', edi830.vendor_id.id
                            # 190905 ning 调整 6分改8分
                            calculate_score = 8  # EDI 830 >> 6分

                    # 2. 在odoo評分區間內有上傳交期
                    domain = []
                    domain = [('vendor_id', 'in', score_list_id.vendor_ids.ids),
                              ('create_date', '<=',today),
                              ('create_date', '>=', class_date_end) ]
                    print '***667', domain
                    for vendor_upload in self.env['iac.tvendor.upload'].sudo().search(domain):
                        if vendor_upload.vendor_id.id in score_list_id.vendor_ids.ids:
                            print '***670', vendor_upload.vendor_id.id
                            # 190905 ning 调整 6分改8分
                            calculate_score = 8  # EDI 830 >> 6分

                    # 交期回復配合度 laura add 20180831 ----e

                    # old laura mark 20180831---s
                    # # 交期准确率，从po查询每个po line中每个物料的delivery_date，检查该物料在gr入料表中最迟一笔入料日期，累计迟交笔数
                    # delay_count = 0
                    # last_year = datetime.now() - timedelta(days=365)
                    # po_lines = self.env['iac.purchase.order.line'].sudo().search([('plant_id', '=', score_list_id.plant_id.id),
                    #                                                        ('vendor_id', 'in',
                    #                                                         score_list_id.vendor_ids.ids),
                    #                                                        ('order_date', '>=',
                    #                                                         fields.Date.to_string(last_year))])
                    # for po_line in po_lines:
                    #     goods_receipt_list = self.env['goods.receipts'].sudo().search(
                    #         [('plant_id', '=', score_list_id.plant_id.id),
                    #          ('document_erp_id', '=', po_line.document_erp_id),
                    #          ('po_line_no', '=', po_line.document_line_erp_id),
                    #          ('movement_type', 'in', ['101', '103', '105'])])
                    #     last_delivery_date = po_line.delivery_date
                    #     for gr in goods_receipt_list:
                    #         if gr.gr_document_date > last_delivery_date:
                    #             last_delivery_date = gr.gr_document_date
                    #     if last_delivery_date > po_line.delivery_date:
                    #         delay_count += 1
                    # score_value = str(delay_count)
                    # for score_range in self.env['iac.score.range'].sudo().search(
                    #         [('log_type', '=', 'VS_P_SHIP_ONTIME')]):
                    #     if delay_count > score_range.range_from and delay_count <= score_range.range_to:
                    #         calculate_score = score_range.score
                    #         break
                    # old laura mark 20180831---e

                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 6, 備料方式
                # Sequence = 6,  EICC回簽時間 laura 20181009 add___s
                # EICC回簽時間<30天 6分 ,<90天 3分,>=90天 2分,未上傳 0分
                # 1. 抓 A33的第一次  "上傳日期"  。Vendor > Doc Control > Other Doc > search status:Active >  找 type : A33
                #  2. 文件A33第一次設定為 Active 的日期減第一筆 GR (good_receipts) 日期。
                elif definition.group_code == 'SCM' and definition.code == 'SCM6' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = ''
                    calculate_score = 0 # 預設 : 未上傳0分
                    self._cr.execute(
                        " select min(A.upload_date) as a33 ,A.vendor_id  " #20181204 laura modify : A33文件的Active 日期 改抓 iac_vendor_attachment 的 upload_date
                        "  from iac_vendor_attachment A,iac_attachment_type t ,iac_vendor v  "
                        "where A.state='active' and t.name='A33' and t.id=A.type and A.vendor_id= v.id  "
                        "    and A.upload_date is not null and A.vendor_id in  (" + vendor_str + ") "
                        "group by A.vendor_id   ")
                    for file in self.env.cr.dictfetchall():
                        print '***800:', file['a33']
                        a33 = file['a33']  # a33 第一次上傳時間

                        vendor = file['vendor_id']
                        print '***801:', vendor
                        vendor = str(vendor)
                        print '***803:', vendor
                        if a33 :  # 有上傳
                            # 190905 ning 调整 2分改4分
                            calculate_score = 4  # 有上傳, 預設 : 2分
                            # 找 第一筆 GR 日期。
                            self._cr.execute(
                                " select '"+a33+"' - min(gr_document_date)  as gr_date from goods_receipts "
                                " where vendor_id in  ("+ vendor + ") " )
                            for gr in self.env.cr.dictfetchall():
                                print '***807:', gr['gr_date'] ,',' , a33
                                gr_date = gr['gr_date']  # 第一筆 GR日期。
                                print '***813:', gr_date
                                EICC = gr_date
                                #EICC = datetime.a33-datetime.gr_date

                                if EICC:
                                    print '***811:', EICC
                                    if EICC < 30:
                                        # 190905 ning 调整 6分改8分
                                        calculate_score = 8  #  <30天 6分
                                    elif EICC >= 30 and EICC < 90 :
                                        # 190905 ning 调整 3分改5分
                                        calculate_score = 5  #  <90天 3分
                                    elif EICC >= 90 :
                                        # 190905 ning 调整 2分改4分
                                        calculate_score = 4  #  >=90天 2分
                        else: # 未上傳0分
                            calculate_score = 0 #  未上傳0分

                    print '***821:',  calculate_score

                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value':score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))

                # Sequence = 7, Forecast回復天數 laura add 20180905 add----s
                # Forecast回復天數 : Reply Supply Plan Date 減 Forecast Release Date。算出每顆料的回覆天數，再取平均值。
                #  平均值3天內6分,平均值4天內4分,平均值5天以上3分

                elif definition.group_code == 'SCM' and definition.code == 'SCM7' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = ''
                    calculate_score = 0

                    # print '***748:',score_list_id.vendor_ids.ids,',',today,',',class_date_end
                    print '***752:',vendor_str,',',today,',',class_date_end

                    self._cr.execute(  " SELECT avg(dd)  as avg "
                                       "from ("
                                       " select confirm.material_id, confirm.vendor_id,(vendor.create_date::date - max(confirm.cdt) ) dd "
                                       " from (   "
                                       "  select distinct create_date::date as cdt, material_id, vendor_id "
                                       "       from iac_tconfirm_data confirm "
                                       "     where status in ('T') "
                                       "         and vendor_id in (" + vendor_str + ")"
                                       "         and to_char(create_date,'yyyy-mm-dd') <= '"+today+"'"
                                       "         and to_char(create_date,'yyyy-mm-dd') >=  '"+class_date_end+"'"
                                       " union "
                                       "    select distinct create_date::date as cdt, material_id, vendor_id "
                                       "     from iac_tconfirm_data_temp confirm_temp "
                                       "    where status in ('T')   and vendor_id in ("+vendor_str+")"
                                       "       and to_char(create_date,'yyyy-mm-dd') <= '"+today+"'"
                                       "       and to_char(create_date,'yyyy-mm-dd') >= '"+class_date_end+"'"
                                       " ) confirm, iac_tvendor_upload vendor"
                                       " where vendor.status in ('T')"
                                       "     and vendor.material_id = confirm.material_id"
                                       "     and vendor.vendor_id = confirm.vendor_id "
                                       " group by confirm.material_id, confirm.vendor_id,  vendor.create_date::date "
                                       " )  A ")
                    for item in self.env.cr.dictfetchall():
                        print '***877:', item['avg']
                        # 190905 ning 调整 3分改6分
                        calculate_score = 6 # 預設 3分

                        if item['avg'] <= 3 : # <3 天 , 6分
                            # 190905 ning 调整 6分改9分
                            calculate_score = 9
                        elif item['avg'] >3 and item['avg'] <=4 : # 4天內 , 4分
                            # 190905 ning 调整 4分改7分
                            calculate_score = 7
                        elif item['avg'] > 4:  # 大於天4天 , 3分
                            # 190905 ning 调整 3分改6分
                            calculate_score = 6

                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 7, Forecast回復天數 laura add 20180905 add----e

                # Sequence = 8, 產地回填率 laura add 20180004 add----s
                #評分區間內該vendor下所有的open po料號distinct數量/有維護 產地country or City 料號數量
                # 產地回填率>=90% 6分。產地回填率<90% 4分。產地回填率<50%  3分。
                # Sequence = 8, 廠商回報的機制能力
                elif definition.group_code == 'SCM' and definition.code == 'SCM8' and definition.part_class.id == part_category_id.part_class.id:
                    # 8.1.評分區間內該vendor下所有的open po 有填country的料號數量
                    # 190905 ning 调整 加上open po的检查
                    self._cr.execute("select count(t.part_id) as c_count from "  
                                            "(select distinct part_id from "
                                            "( select  po_line.part_id,sum(COALESCE(po_line.quantity,0))-sum(COALESCE(gr.qty_received,0)) as open_po "
                                            "from iac_purchase_order po "
			                                "INNER JOIN iac_purchase_order_line po_line on po.id = po_line.order_id and po_line.odoo_deletion_flag = 'f' "
			                                "inner  JOIN	iac_country_origin country on country.material = po_line.part_id and ( country.country_id is not null or country.city is not null ) "
			                                "left JOIN goods_receipts gr on gr.po_id = po.id and gr.po_line_id = po_line.id and gr.part_id = po_line.part_id "
                                            "where po.vendor_id in (" + vendor_str + ") "
                                            "and po.order_date >= '" + class_date_end + "' "
                                            "and po.order_date <= '" + today + "' "
                                            "GROUP BY po_line.part_id ) Country_count where open_po>0 ) t ")
                    for item in self.env.cr.dictfetchall():
                        print '***875:', item['c_count']  # 8.1.  評分區間內該vendor下所有的open po 有填country的料號數量
                        c_count = item['c_count']

                    # 8.2.評分區間內該vendor下所有的open po 料號數量
                    # 190905 ning 调整 加上open po的检查
                    self._cr.execute("select count(t.part_id) as o_count from "
			                            "(select DISTINCT part_id from "
                                        "(  select  po_line.part_id,sum(COALESCE(po_line.quantity,0))-sum(COALESCE(gr.qty_received,0)) as open_po "
                                        "from iac_purchase_order po "
				                        "INNER JOIN iac_purchase_order_line po_line on po.id = po_line.order_id and po_line.odoo_deletion_flag='f' "
				                        "LEFT JOIN goods_receipts gr on gr.po_id = po.id and gr.po_line_id=po_line.id and gr.part_id = po_line.part_id "
                                        "where  po.vendor_id in (" + vendor_str + ") "
                                        "and po.order_date  >=  '" + class_date_end + "' "
                                        "and  po.order_date <= '" + today + "' "
                                        "GROUP BY po_line.part_id) Openpo_count where open_po>0) t ")
                    for item in self.env.cr.dictfetchall():
                        print '***832:', item['o_count']  #  8.2.評分區間內該vendor下所有的open po 料號數量
                        o_count = item['o_count']

                    country_rate = 0

                    if o_count ==0 :
                        print '***836:' ,country_rate
                        country_rate = 0
                    else:
                        print '***839:', country_rate
                        country_rate = ( c_count / o_count ) *100

                    print '***842:', country_rate

                    score_value = ''

                    if country_rate >=90:
                        # 190905 ning 调整 6分改8分
                        calculate_score = 8  # 產地回填率>=90% 6分。
                    elif country_rate >= 50 and country_rate < 90:
                        # 190905 ning 调整 4分改6分
                        calculate_score = 6  #產地回填率<90% 4分。
                    else:
                        # 190905 ning 调整 3分改5分
                        calculate_score = 5  # 預設 3分 & 產地回填率<50%  3分。

                    print '*853:',country_rate,'。',c_count,'。',o_count,'。',calculate_score

                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))

                # Sequence = 8, 產地回填率 laura add 20180004 add----e

                # SCM-Sequence = 9,  不用了 20180830 laura mark ----s
                # # Sequence = 9, 市場訊息
                # elif definition.group_code == 'SCM' and definition.code == 'SCM9' and definition.part_class.id == part_category_id.part_class.id:
                #     score_value = ''
                #     calculate_score = 0
                #     part_category_line_id = {
                #         'vs_def_id': definition.id,
                #         'score_value': score_value,
                #         'calculate_score': calculate_score,
                #         'user_score':calculate_score,
                #         'score_snapshot': score_snapshot,
                #         'supplier_company_id':pg_gr_row["supplier_company_id"],
                #         'score_list_id':score_list_id.id,
                #         'plant_id':score_list_id.plant_id.id,
                #         'part_category_id':pg_gr_row['part_category_id'],
                #     }
                #     part_category_line_ids.append((0, 0, part_category_line_id))
                # SCM-Sequence = 9,  不用了 20180830 laura mark ----e

                # SCM-Sequence = 10,  不用了 20180830 laura mark ----s
                # Sequence = 10, 緊急插單入料配合
                # elif definition.group_code == 'SCM' and definition.code == 'SCM10' and definition.part_class.id == part_category_id.part_class.id:
                #     score_value = ''
                #     calculate_score = 0
                #     part_category_line_id = {
                #         'vs_def_id': definition.id,
                #         'score_value': score_value,
                #         'calculate_score': calculate_score,
                #         'user_score':calculate_score,
                #         'score_snapshot': score_snapshot,
                #         'supplier_company_id':pg_gr_row["supplier_company_id"],
                #         'score_list_id':score_list_id.id,
                #         'plant_id':score_list_id.plant_id.id,
                #         'part_category_id':pg_gr_row['part_category_id'],
                #     }
                #     part_category_line_ids.append((0, 0, part_category_line_id))
                # SCM-Sequence = 10,  不用了 20180830 laura mark ----e
                # SCM-Sequence = 11,  不用了 20180830 laura mark ----s
                # Sequence = 11, 砍單和延後交期之配合性
                # elif definition.group_code == 'SCM' and definition.code == 'SCM11' and definition.part_class.id == part_category_id.part_class.id:
                #     score_value = ''
                #     calculate_score = 0
                #     part_category_line_id = {
                #         'vs_def_id': definition.id,
                #         'score_value': score_value,
                #         'calculate_score': calculate_score,
                #         'user_score':calculate_score,
                #         'score_snapshot': score_snapshot,
                #         'supplier_company_id':pg_gr_row["supplier_company_id"],
                #         'score_list_id':score_list_id.id,
                #         'plant_id':score_list_id.plant_id.id,
                #         'part_category_id':pg_gr_row['part_category_id'],
                #     }
                #     part_category_line_ids.append((0, 0, part_category_line_id))
                # SCM-Sequence = 11,  不用了 20180830 laura mark ----e

                # QM
                # Sequence = 1, IQC廠商重工次數 废弃
                # elif definition.group_code == 'QM' and definition.code == 'QM1' and definition.part_class.id == part_category_id.part_class.id:
                #     score_value = ''
                #     calculate_score = 0
                #     part_category_line_id = {
                #         'vs_def_id': definition.id,
                #         'score_value': score_value,
                #         'calculate_score': calculate_score,
                #         'user_score':calculate_score,
                #         'score_snapshot': score_snapshot,
                #         'supplier_company_id':pg_gr_row["supplier_company_id"],
                #         'score_list_id':score_list_id.id,
                #         'plant_id':score_list_id.plant_id.id,
                #         'part_category_id':pg_gr_row['part_category_id'],
                #     }
                #     part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 2, 材料QRQC次數 待定
                elif definition.group_code == 'QM' and definition.code == 'QM2' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = ''
                    calculate_score = 10
                    vendor_obj_list = []
                    qrqc_list = []
                    for sc_line in self.env['iac.supplier.company.line'].search([('supplier_company_id','=',score_list_id.supplier_company_id.id)]):
                        vendor_obj_list.append(sc_line.vendor_id)
                    for vendor in vendor_obj_list:
                        if vendor.plant.id == score_list_id.plant_id.id:
                            for item in self.env['qrqc.data.for.scoring.vs'].search([('vendor_id','=',vendor.id),
                                                            ('plant_id','=',score_list_id.plant_id.id),
                                                            ('operatedate','>=',class_date_end),
                                                            ('operatedate','<=',today)]):
                                qrqc_list.append(item)
                    if len(qrqc_list) == 0:
                        calculate_score = 10
                        score_value = '0'
                    elif len(qrqc_list) == 1:
                        calculate_score = 8
                        score_value = '1'
                    elif len(qrqc_list) == 2:
                        calculate_score = 6
                        score_value = '2'
                    elif len(qrqc_list) == 3:
                        calculate_score = 4
                        score_value = '3'
                    elif len(qrqc_list) == 4:
                        calculate_score = 2
                        score_value = '4'
                    else:
                        calculate_score = 0
                        score_value = str(len(qrqc_list))
                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 3, 案件處理時效性(8D report追蹤時效性) 废弃
                # elif definition.group_code == 'QM' and definition.code == 'QM3' and definition.part_class.id == part_category_id.part_class.id:
                #     score_value = ''
                #     calculate_score = 0
                #     part_category_line_id = {
                #         'vs_def_id': definition.id,
                #         'score_value': score_value,
                #         'calculate_score': calculate_score,
                #         'user_score':calculate_score,
                #         'score_snapshot': score_snapshot,
                #         'supplier_company_id':pg_gr_row["supplier_company_id"],
                #         'score_list_id':score_list_id.id,
                #         'plant_id':score_list_id.plant_id.id,
                #         'part_category_id':pg_gr_row['part_category_id'],
                #     }
                #     part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 4, 客訴問題次數 废弃
                # elif definition.group_code == 'QM' and definition.code == 'QM4' and definition.part_class.id == part_category_id.part_class.id:
                #     score_value = ''
                #     calculate_score = 0
                #     part_category_line_id = {
                #         'vs_def_id': definition.id,
                #         'score_value': score_value,
                #         'calculate_score': calculate_score,
                #         'user_score':calculate_score,
                #         'score_snapshot': score_snapshot,
                #         'supplier_company_id':pg_gr_row["supplier_company_id"],
                #         'score_list_id':score_list_id.id,
                #         'plant_id':score_list_id.plant_id.id,
                #         'part_category_id':pg_gr_row['part_category_id'],
                #     }
                #     part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 5, 失败成本，逻辑重写
                elif definition.group_code == 'QM' and definition.code == 'QM5' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = '0'
                    calculate_score = 6
                    fail_cost = 0
                    vendor_obj_list = []
                    for sc_line in self.env['iac.supplier.company.line'].search(
                            [('supplier_company_id', '=', score_list_id.supplier_company_id.id)]):
                        vendor_obj_list.append(sc_line.vendor_id)
                    for vendor in vendor_obj_list:
                        if vendor.plant.id == score_list_id.plant_id.id:
                            for item in self.env['fail.cost.for.scoring.vs'].search([('vendor_id', '=', vendor.id),
                                                                                     ('plant_id', '=',
                                                                                      score_list_id.plant_id.id),
                                                                                     ('appdate', '>=',
                                                                                      class_date_end),
                                                                                     ('appdate', '<=', today)]):
                                # qrqc_list.append(item)
                                fail_cost+=item.realpay
                    score_value = str(fail_cost)
                    if fail_cost>0 and fail_cost <= 500:
                        calculate_score = 6
                    elif fail_cost>500 and fail_cost <= 1000:
                        calculate_score = 5
                    elif fail_cost>1000 and fail_cost <= 2500:
                        calculate_score = 3
                    elif fail_cost>2500 and fail_cost <= 5000:
                        calculate_score = 2
                    elif fail_cost>5000:
                        calculate_score = 0


                    # fail_cost = 0
                    # fail_qty = 0
                    # fail_not_zero = [] #存入数量和单价都不为0的失败成本
                    #
                    # if pg_iqc_result:
                    #     fail_cost_query = """
                    #                 SELECT vwid.plant_id,
                    #                     vwid.part_id,
                    #                     vwid.vendor_id,
                    #                     sum(vwid.tc_qty)+ sum(vwid.return_qty) as fail_qty,
                    #                     mm.price,
                    #                     mm.price_unit
                    #                     FROM vs_webflow_iqc_data vwid
                    #                     INNER JOIN iac_vendor v on v.id = vwid.vendor_id
                    #                     INNER JOIN material_map mm on mm.part_no = vwid.part_no and mm.plant_code = vwid.plant_code
                    #                     inner join material_master pn on pn.part_no = vwid.part_no and pn.plant_code = vwid.plant_code
                    #                     INNER JOIN iac_supplier_company sc on v.supplier_company_id = sc.id
                    #                     inner JOIN iac_part_category_material_group_history ipcm on ipcm.material_group_id = pn.material_group_id
                    #                     where to_date((vwid.cdt),'yyyymm') >= %s and (vwid.return_qty > 0 or vwid.tc_qty >0)
                    #                       and v.supplier_company_id=%s and ipcm.score_snapshot = %s and vwid.plant_id=%s and ipcm.part_category_id=%s
                    #                     GROUP BY vwid.plant_id,vwid.part_id,mm.price,mm.price_unit,vwid.vendor_id
                    #                                      """
                    #     # 防止class_date为空
                    #     if score_list_id.supplier_company_id.class_date:
                    #         class_date = score_list_id.supplier_company_id.class_date
                    #     else:
                    #         class_date = score_list_id.supplier_company_id.create_date
                    #     params = (class_date,pg_iqc_result['supplier_company_id'],score_snapshot,pg_iqc_result['plant_id'],pg_iqc_result['part_category_id'])
                    #     self.env.cr.execute(fail_cost_query, params)
                    #     fail_cost_result = self.env.cr.dictfetchall()
                    #     if fail_cost_result:
                    #         for fail in fail_cost_result:
                    #             fail_qty = fail['fail_qty']
                    #             if fail_qty == 0:
                    #                 continue
                    #             else:
                    #                 if fail['price_unit'] != 0 and fail['price'] != 0:
                    #                     fail_not_zero.append(fail)
                    #                     #单价
                    #                     unit_price = fail['price']/fail['price_unit']
                    #
                    #                     rate_query = """
                    #                                         SELECT
                    #                                             (ice.to_currency_amount/ice.from_currency_amount) as rate
                    #                                              from iac_currency_exchange ice
                    #                                             INNER JOIN res_currency rc on ice.from_currency_id = rc.id
                    #                                             where state='active' and rc.name=%s
                    #                                                 """
                    #                     #判断当前厂区
                    #                     if fail['plant_id'] == 41:
                    #                         money = 'TWD'
                    #                     else:
                    #                         money = 'RMB'
                    #                     params = (money,)
                    #                     self.env.cr.execute(rate_query,params)
                    #                     rate_result = self.env.cr.dictfetchone()
                    #                     # 汇率
                    #                     rate = rate_result['rate']
                    #                     fail_cost += fail_qty*unit_price*rate
                    #                 else:
                    #                     continue
                    #         if len(fail_not_zero) > 0:
                    #             score_value = str(fail_cost)
                    #             for cost in self.env['iac.score.iqc.mprma.history'].sudo().search(
                    #                     [('score_snapshot', '=', score_snapshot),
                    #                      ('part_category_id', '=', part_category_id.id),
                    #                      ('score_type', '=', '失败成本')]):
                    #                 if fail_cost > cost.lower_limit and fail_cost <= cost.high_limit:
                    #                     calculate_score = cost.score
                    #                     break
                    #         else:
                    #             calculate_score = 6
                    #     else:
                    #         calculate_score = 6
                        # fail_cost = pg_iqc_result['lurking_cost'] + pg_iqc_result['hardness_cost']
                        # score_value = str(fail_cost)
                    # for cost in self.env['iac.fail.cost.section.history'].sudo().search(
                    #         [('score_snapshot', '=', score_snapshot)]):
                    #     if fail_cost > cost.lower_limit and fail_cost <= cost.high_limit:
                    #         calculate_score = cost.score
                    #         break
                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 6, 入料MA PPM
                elif definition.group_code == 'QM' and definition.code == 'QM6' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = '0'
                    calculate_score = 0
                    mappm = 0
                    if pg_iqc_result:
                        mappm = pg_iqc_result['gr_mappm']
                        score_value = str(mappm)
                    for iqc_mprma in self.env['iac.score.iqc.mprma.history'].sudo().search(
                            [('score_snapshot', '=', score_snapshot), ('part_category_id', '=', part_category_id.id),
                             ('score_type', '=', '入料MA')]):
                        if mappm > iqc_mprma.lower_limit and mappm <= iqc_mprma.high_limit:
                            calculate_score = iqc_mprma.score
                            break
                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 7, 入料MI PPM
                elif definition.group_code == 'QM' and definition.code == 'QM7' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = '0'
                    calculate_score =0
                    mippm = 0
                    if pg_iqc_result:
                        mippm = pg_iqc_result['gr_mippm']
                        score_value = str(mippm)
                    for iqc_mprma in self.env['iac.score.iqc.mprma.history'].sudo().search(
                            [('score_snapshot', '=', score_snapshot), ('part_category_id', '=', part_category_id.id),
                             ('score_type', '=', '入料MI')]):
                        if mippm > iqc_mprma.lower_limit and mippm <= iqc_mprma.high_limit:
                            calculate_score = iqc_mprma.score
                            break
                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 8, LRR
                elif definition.group_code == 'QM' and definition.code == 'QM8' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = '0'
                    calculate_score = 0
                    lrr = 0
                    if pg_iqc_result:
                        lrr = pg_iqc_result['lrr']
                        score_value = str(lrr)
                    for iqc_mprma in self.env['iac.score.iqc.mprma.history'].sudo().search(
                            [('score_snapshot', '=', score_snapshot), ('part_category_id', '=', part_category_id.id),
                             ('score_type', '=', 'LRR')]):
                        if lrr > iqc_mprma.lower_limit and lrr <= iqc_mprma.high_limit:
                            calculate_score = iqc_mprma.score
                            break
                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 9, 特採率 废弃
                # elif definition.group_code == 'QM' and definition.code == 'QM9' and definition.part_class.id == part_category_id.part_class.id:
                #     score_value = '0'
                #     calculate_score = 0
                #     tc = 0
                #     if pg_iqc_result:
                #         tc = pg_iqc_result['tc_qty']
                #         score_value = str(tc)
                #     for iqc_mprma in self.env['iac.score.iqc.mprma.history'].sudo().search(
                #             [('score_snapshot', '=', score_snapshot), ('part_category_id', '=', part_category_id.id),
                #              ('score_type', '=', '特採率')]):
                #         if tc > iqc_mprma.lower_limit and tc <= iqc_mprma.high_limit:
                #             calculate_score = iqc_mprma.score
                #             break
                #     part_category_line_id = {
                #         'vs_def_id': definition.id,
                #         'score_value': score_value,
                #         'calculate_score': calculate_score,
                #         'user_score':calculate_score,
                #         'score_snapshot': score_snapshot,
                #         'supplier_company_id':pg_gr_row["supplier_company_id"],
                #         'score_list_id':score_list_id.id,
                #         'plant_id':score_list_id.plant_id.id,
                #         'part_category_id':pg_gr_row['part_category_id'],
                #     }
                #     part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 10, 退料PPM，退料MA PPM + 退料MI PPM
                elif definition.group_code == 'QM' and definition.code == 'QM10' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = '0'
                    calculate_score = 0
                    return_ppm = 0
                    if pg_iqc_result:
                        return_ppm = pg_iqc_result['return_mappm']
                        score_value = str(return_ppm)
                    for iqc_mprma in self.env['iac.score.iqc.mprma.history'].sudo().search(
                            [('score_snapshot', '=', score_snapshot), ('part_category_id', '=', part_category_id.id),
                             ('score_type', '=', '退料PPM')]):
                        if return_ppm > iqc_mprma.lower_limit and return_ppm <= iqc_mprma.high_limit:
                            calculate_score = iqc_mprma.score
                            break
                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 11, ISO證書達成情況
                elif definition.group_code == 'QM' and definition.code == 'QM11' and definition.part_class.id == part_category_id.part_class.id:
                    score_value = ''
                    calculate_score = 0
                    vendor_reg_ids = []
                    for vendor in score_list_id.vendor_ids:
                        vendor_reg_ids.append(vendor.vendor_reg_id.id)
                    vendor_attachment_list = self.env['iac.vendor.register.attachment'].sudo().search(
                        [('vendor_reg_id', 'in', vendor_reg_ids),
                         ('expiration_date', '>', fields.Date.today())])
                    iso9001_file = -5
                    iso14001_file = 0
                    ts16949_file = 0
                    ohsas18000_file = 0
                    qc080000_file = 0
                    iso13485_file = 0
                    for file in vendor_attachment_list:
                        if file.type.name == 'A07':
                            iso9001_file = 0
                        elif file.type.name == 'A08':
                            iso14001_file = 1
                        elif file.type.name == 'A09':
                            ts16949_file = 1
                        elif file.type.name == 'A10':
                            ohsas18000_file = 1
                        elif file.type.name == 'A11':
                            qc080000_file = 1
                        elif file.type.name == 'A17':
                            iso13485_file = 1
                    calculate_score = iso9001_file + iso14001_file + ts16949_file + ohsas18000_file + qc080000_file + iso13485_file
                    score_value = str(calculate_score)
                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))
                # Sequence = 12, 年度稽核成績 废弃
                # elif definition.group_code == 'QM' and definition.code == 'QM12' and definition.part_class.id == part_category_id.part_class.id:
                #     score_value = ''
                #     calculate_score = 0
                #     part_category_line_id = {
                #         'vs_def_id': definition.id,
                #         'score_value': score_value,
                #         'calculate_score': calculate_score,
                #         'user_score':calculate_score,
                #         'score_snapshot': score_snapshot,
                #         'supplier_company_id':pg_gr_row["supplier_company_id"],
                #         'score_list_id':score_list_id.id,
                #         'plant_id':score_list_id.plant_id.id,
                #         'part_category_id':pg_gr_row['part_category_id'],
                #     }
                #     part_category_line_ids.append((0, 0, part_category_line_id))
                elif definition.part_class.id == part_category_id.part_class.id:
                    score_value = ''
                    calculate_score = 0
                    part_category_line_id = {
                        'vs_def_id': definition.id,
                        'score_value': score_value,
                        'calculate_score': calculate_score,
                        'user_score':calculate_score,
                        'score_snapshot': score_snapshot,
                        'supplier_company_id':pg_gr_row["supplier_company_id"],
                        'score_list_id':score_list_id.id,
                        'plant_id':score_list_id.plant_id.id,
                        'part_category_id':pg_gr_row['part_category_id'],
                    }
                    part_category_line_ids.append((0, 0, part_category_line_id))

            # 生成SC各site各part_category的score
            score_part_category_vals = {
                'score_list_id': score_list_id.id,
                'part_category_id': pg_gr_row['part_category_id'],
                'line_ids': part_category_line_ids,
                # 'scm_controller_id': scm_controller_id,
                # 'scm_partner_id': scm_partner_id,
                # 'qm_controller_id': qm_controller_id,
                # 'qm_leader_id': qm_leader_id,
                # 'qm_partner_id': qm_partner_id,
                'gr_qty': pg_gr_row['gr_qty'],
                'gr_amount': gr_amount,
                'score_snapshot': score_snapshot,
                'supplier_company_id':pg_gr_row["supplier_company_id"],
                'plant_id':score_list_id.plant_id.id,
            }
            score_part_category_ids.append((0, 0, score_part_category_vals))

        # 生成supplier company score
        if len(score_part_category_ids)>0:
            score_sc_vals = {
                'score_list_id': score_list_id.id,
                # 'scm_controller_id': scm_controller_id,
                # 'qm_controller_id': qm_controller_id,
                # 'qm_leader_id': qm_leader_id,
                'score_part_category_ids': score_part_category_ids,
                'score_snapshot': score_snapshot,
                'supplier_company_id':score_list_id.supplier_company_id.id,
                'plant_id':score_list_id.plant_id.id
            }
            score_sc_rec=self.env['iac.score.supplier_company'].sudo().create(score_sc_vals)
            score_sc_rec.env.cr.commit()

    @api.model
    def create_class_part_data(self, score_snapshot):
        """
        score.part.category 数据生成后生成 class.part.category的数据
        建立2个模型之间的关联
        :param score_snapshot:
        :return:
        """
        domain_score_part=[
            ('score_snapshot','=',score_snapshot)
        ]
        score_part_cate_list=self.env["iac.score.part_category"].sudo().search(domain_score_part)
        for score_part_cate in score_part_cate_list:
            domain_class_part=[
                ('supplier_company_id', '=', score_part_cate.supplier_company_id.id),
                ('part_category_id', '=', score_part_cate.part_category_id.id),
                ('score_snapshot', '=', score_snapshot)
            ]
            class_part_category_id = self.env['iac.class.part_category'].sudo().search(domain_class_part)
            #如果class.part.cate 不存在那么创建相关记录
            if not class_part_category_id:
                # 组装part category score数据，相同part category，不同plant的会汇总到score_part_category_ids上
                pc_class_vars = {
                    'supplier_company_id': score_part_cate.supplier_company_id.id,
                    'part_category_id': score_part_cate.part_category_id.id,
                    'score_snapshot': score_part_cate.score_snapshot,
                    # 'scm_controller_id': score_part_cate.scm_controller_id.id,
                    # 'qm_controller_id': score_part_cate.qm_controller_id.id,
                    # 'qm_leader_id': score_part_cate.qm_leader_id.id,
                }
                class_part_category_id=self.env['iac.class.part_category'].sudo().create(pc_class_vars)
            #建立关联数据
            # score_part_cate.write({"class_part_category_id":class_part_category_id.id})

            super(IacScorePartCategory,score_part_cate).write({"class_part_category_id":class_part_category_id.id})

    @api.model
    def create_class_company_data(self, score_snapshot):
        """
        class.part.category 数据生成后生成 class.supplier的数据
        建立2个模型之间的关联
        首先计算iac.class.
        iac.score.supplier_company 与 iac.class.supplier_company 与之间的模型关联建立
        :param score_snapshot:
        """
        domain_class=[
            ('score_snapshot','=',score_snapshot)
        ]
        class_part_list=self.env["iac.class.part_category"].sudo().search(domain_class)
        for class_part in class_part_list:
            domain_company=[
                ('supplier_company_id', '=', class_part.supplier_company_id.id),
                ('score_snapshot', '=', score_snapshot)
            ]
            class_company=self.env["iac.class.supplier_company"].search(domain_company,limit=1)
            if not class_company:
                sc_class_vars = {
                    'supplier_company_id': class_part.supplier_company_id.id,
                    #'score_supplier_company_ids': [(6, 0, [x.id for x in score_supplier_company_ids])],
                    #'class_part_category_ids': [(6, 0, [x.id for x in class_part_category_ids])],
                    'score_snapshot': score_snapshot
                }
                class_company=self.env['iac.class.supplier_company'].sudo().create(sc_class_vars)
            class_part.write({"class_supplier_company_id":class_company.id})


        #iac.score.supplier_company 与 iac.class.supplier_company 与之间的模型关联建立
        domain_company=[
             ('score_snapshot','=',score_snapshot)
        ]
        #建立score.supplier_company 与class.supplier_company之间的关联
        score_company_list=self.env["iac.score.supplier_company"].search(domain_company)
        for score_company in score_company_list:
            domain_class_company=[
                ('supplier_company_id', '=', score_company.supplier_company_id.id),
                ('score_snapshot', '=', score_snapshot)
            ]
            class_company=self.env["iac.class.supplier_company"].search(domain_class_company,limit=1)
            if class_company:
                score_company.write({"class_supplier_company_id":class_company.id})



        #更新part_category中的weight 和汇总明细项目获取分数信息
        domain_part=[
            ('score_snapshot', '=', score_snapshot)
        ]
        score_part_list=self.env["iac.score.part_category"].search(domain_part)
        for score_part_rec in score_part_list:
            score_part_rec._update_part_category_score_data()


        #更新score.supplier_company模型中 weight 数据
        domain_company=[
             ('score_snapshot','=',score_snapshot)
        ]
        class_company_list=self.env["iac.class.supplier_company"].search(domain_company)
        for class_company in class_company_list:
            self.env["iac.score.supplier_company"].update_weight(class_company.supplier_company_id.id,score_snapshot)


    @api.model
    def update_class_part_2_class_company(self, score_snapshot):
        """
        class.part.category 建立关联 class.supplier的数据
        :param score_snapshot:
        """
        domain_class=[
            ('score_snapshot','=',score_snapshot)
        ]
        class_part_list=self.env["iac.class.part_category"].sudo().search(domain_class)
        for class_part in class_part_list:
            domain_company=[
                ('supplier_company_id', '=', class_part.supplier_company_id.id),
                ('score_snapshot', '=', score_snapshot)
            ]
            class_company=self.env["iac.class.supplier_company"].search(domain_company,limit=1)
            if  class_company:
                class_part.write({"class_supplier_company_id":class_company.id})