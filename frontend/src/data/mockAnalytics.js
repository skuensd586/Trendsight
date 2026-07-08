export const clusterPoints = [
  { title: '南方强降雨救援信息快速扩散', cluster: '暴雨救援', x: 1.2, y: 3.6, heat: 94, risk: '高' },
  { title: '城市主干道积水求助集中出现', cluster: '暴雨救援', x: 1.6, y: 3.2, heat: 78, risk: '中' },
  { title: '临时停水通知传播引发居民咨询', cluster: '公共服务', x: 3.8, y: 1.4, heat: 39, risk: '低' },
  { title: '城市轨道交通延误事件官方回应', cluster: '交通出行', x: 4.1, y: 3.1, heat: 81, risk: '中' },
  { title: '雷雨天气导致航班延误补偿讨论', cluster: '交通出行', x: 4.4, y: 3.5, heat: 56, risk: '中' },
  { title: '新能源车售后争议引发集中讨论', cluster: '消费权益', x: 6.1, y: 2.8, heat: 87, risk: '中高' },
  { title: '社区团购配送延迟投诉扩散', cluster: '消费权益', x: 6.4, y: 2.2, heat: 58, risk: '低' },
  { title: '高校食堂价格调整话题升温', cluster: '教育民生', x: 2.8, y: 5.4, heat: 72, risk: '中' },
  { title: '资格考试考点安排变化引发咨询', cluster: '教育民生', x: 3.1, y: 5.8, heat: 49, risk: '低' },
  { title: '医院挂号平台排队异常引关注', cluster: '医疗民生', x: 5.2, y: 5.1, heat: 69, risk: '中' },
];

export const propagationSankey = {
  nodes: [
    { name: '社区求助帖' },
    { name: '本地博主' },
    { name: '短视频平台' },
    { name: '微博热搜' },
    { name: '新闻客户端' },
    { name: '应急部门通报' },
    { name: '辟谣账号' },
    { name: '公众讨论' },
  ],
  links: [
    { source: '社区求助帖', target: '本地博主', value: 18 },
    { source: '本地博主', target: '短视频平台', value: 22 },
    { source: '短视频平台', target: '微博热搜', value: 26 },
    { source: '微博热搜', target: '新闻客户端', value: 19 },
    { source: '社区求助帖', target: '应急部门通报', value: 12 },
    { source: '应急部门通报', target: '新闻客户端', value: 16 },
    { source: '应急部门通报', target: '辟谣账号', value: 8 },
    { source: '新闻客户端', target: '公众讨论', value: 24 },
    { source: '微博热搜', target: '公众讨论', value: 31 },
    { source: '辟谣账号', target: '公众讨论', value: 6 },
  ],
};

export const credibilityFactors = [
  { name: '官方信源一致性', value: 92 },
  { name: '多源交叉出现', value: 88 },
  { name: '文本重复率正常', value: 81 },
  { name: '高风险词可控', value: 76 },
  { name: '传播链路完整', value: 84 },
];
