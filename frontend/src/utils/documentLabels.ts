const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  acceptance_proof: '验收证明',
  acceptance_report: '验收报告',
  bid_announcement: '招标公告',
  bid_document: '招标文件',
  bid_result: '中标结果',
  contract: '合同文件',
  economic_benefit_report: '经济效益报告',
  meeting_material: '会议材料',
  meeting_minutes: '会议纪要',
  negotiation_report: '谈判记录',
  oa_screenshot: 'OA截图',
  payment_voucher: '付款凭证',
  post_review_report: '后评价报告',
  single_source_report: '单一来源说明',
  supplementary_contract: '补充合同',
  supplier_quote: '供应商报价',
};

export function documentLabel(docType: string): string {
  return DOCUMENT_TYPE_LABELS[docType] ?? docType;
}
