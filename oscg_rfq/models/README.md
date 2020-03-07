    @api.model
    def job_asn_vmi(self):
    '''发起api调用，根据返回数据按行生成asn，主要校验po/max数量，全部成功or失败，调用sap api返回创建结果。
        主動調用 SAP 接口獲取 VMI ASN header 和 Item資料, 一個header 開在一張 ASN 裡面,
        一期二期的處理要特別注意，現在應該是作為英五廠與浦東廠區分在用,
        不同的 Storage Location不能開在同一張 ASN 中 ,需要做 vendor , plant , Material, PO 的有效性檢查,
        同樣要檢查Open PO, 最大可交量, 開立ASN 后要更新 Open PO 和最大可較量資料,
        無論成功或失敗都要調用 SAP 接口寫回 SAP , 成功要寫 ASN 號碼, 失敗要寫明失敗原因.
        生成的 ASN 同樣要一筆一筆上傳 SAP , SAP 上同步創建 ASN
          "Document" : {
            "HEADER" : [ {
              "PLANT_ID" : "CP21",
              "VMI_CODE" : "B",
              "PULL_SIGNAL_ID" : "B380077170905",
              "ITEM_COUNTS" : "1",
              "OWNER" : "IAC",
              "ITEM" : [ {
                "PS_ITEM" : "10",
                "VENDOR_ERP_ID" : "380077",
                "PO_NO" : "4500123456",
                "PO_ITEM" : "10",
                "PART_NO" : "6024A0015601",
                "PULL_QTY" : "100",
                "MEINS" : "EA"
              }, {
                "PS_ITEM" : "20",
                "VENDOR_ERP_ID" : "380077",
                "PO_NO" : "4500123456",
                "PO_ITEM" : "20",
                "PART_NO" : "6024A0015602",
                "PULL_QTY" : "200",
                "MEINS" : "EA"
              } ]
            } ]
          }
        '''


        最大可交量失败，后续继续处理，【一周以内要处理】
        其他失败／相关组都失败。后续不处理。