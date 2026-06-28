# EnterpriseRAG-Guard：面向企业知识库代理的可迁移提示注入防御框架

小组项目论文内容稿（无封面版）

本 Markdown 文件用于快速修改正文内容；正式排版版本见同目录 DOCX。

EnterpriseRAG-Guard：面向企业知识库代理的可迁移提示注入防御框架

小组项目论文初稿（无封面版）


## 摘要

随着大语言模型在企业知识管理、员工服务和合规问答中的应用不断增加，基于检索增强生成（Retrieval-Augmented Generation, RAG）的企业知识库代理逐渐成为组织内部信息查询的重要入口。然而，RAG 系统在引入外部或内部文档作为上下文证据时，也扩大了提示注入攻击的暴露面。攻击者既可以在用户问题中直接嵌入“忽略规则”“泄露凭证”等恶意指令，也可以通过被检索文档间接影响模型，使系统伪造政策、跨企业引用、泄露敏感信息或使用不可信证据。

本项目设计并实现 EnterpriseRAG-Guard，一套面向企业专属知识库代理的可迁移提示注入防御框架。系统不是构建一个混合回答所有企业问题的跨企业代理，而是将每家企业视为独立知识边界：Company Agent = Universal Security Core + Company Security Profile + Company Knowledge Base。通用安全核心负责风险检测、来源可信检索、证据隔离、事实抽取、引用验证以及修复/拒答；企业安全配置负责定义企业 ID、允许来源、敏感字段、风险阈值和引用要求；企业知识库则由该企业自己的公开资料或未来客户接入数据构成。

在实验中，项目构建了覆盖 Made Tech、GitLab、Basecamp、Valve、腾讯、比亚迪和华为的多企业语料，共 1084 个去重知识片段，包含中文与英文、HTML 与 PDF、员工政策、治理、风险、合规和社会责任等不同类型文档。评测集包含 224 个正常与攻击问题，覆盖直接用户注入、凭证索取、跨公司污染、自适应政策修订和检索文档投毒等攻击面。结果显示，在当前评测集上，完整防御 B7 将攻击成功率从普通 RAG 的 89.29% 降至 25.00%，引用错误率从 58.48% 降至 0，投毒存活率从 100% 降至 0。

除研究原型外，本项目进一步将系统产品化为企业 RAG 安全网关与接入平台，增加租户接入、统一连接器、安全摄取管道、租户级安全配置和可视化网站。网站支持员工查询、红队挑战、控制组与安全组对照、防御过程追踪、可信证据与隔离区展示，以及“创建企业安全 Agent”的接入向导。本文总结项目背景、相关研究、方法设计、实验结果、系统实现、局限性与小组分工。

关键词：检索增强生成；提示注入；企业知识库；安全网关；多租户隔离；引用验证


## Abstract

Large language models are increasingly used as enterprise knowledge assistants for human resources, compliance, IT support, and internal policy question answering. Retrieval-Augmented Generation (RAG) improves factual grounding by adding retrieved documents to the model context, but it also introduces new security risks. Malicious instructions can appear either in the user query or in retrieved documents, causing the agent to fabricate policies, leak credentials, cite poisoned evidence, or confuse the policies of different companies.

This project proposes EnterpriseRAG-Guard, a transferable defense framework for company-specific RAG agents. The system does not build a single mixed cross-company agent. Instead, each company has its own knowledge boundary and is modeled as: Company Agent = Universal Security Core + Company Security Profile + Company Knowledge Base. The universal security core performs query risk detection, provenance-aware retrieval, evidence isolation, claim extraction, citation verification, repair, and refusal. The company profile defines allowed sources, sensitive fields, risk thresholds, and citation requirements.

The evaluation corpus contains 1,084 chunks from seven companies: Made Tech, GitLab, Basecamp, Valve, Tencent, BYD, and Huawei. The dataset covers Chinese and English documents, HTML pages, PDFs, employee policies, governance, risk, compliance, and sustainability information. A 224-case evaluation set is used to test normal questions and attacks including user-query injection, credential extraction, cross-company contamination, adaptive policy amendments, and retrieved-document poisoning. On this benchmark, the full B7 guard reduces attack success rate from 89.29% to 25.00%, citation error rate from 58.48% to 0, and poison survival rate from 100% to 0.

Beyond the research prototype, the project implements a product-style enterprise RAG security platform with tenant onboarding, connector abstractions, secure ingestion, tenant profiles, and a Chinese-first web interface. The demo supports employee queries, red-team challenges, control-vs-secure comparison, defense trace visualization, safe evidence inspection, quarantine panels, and a “Create Your Company Agent” onboarding workflow. This paper presents the motivation, literature review, method, implementation, experiment design, result analysis, limitations, conclusion, and team contribution.

Key words: Retrieval-Augmented Generation; prompt injection; enterprise knowledge agent; security gateway; tenant isolation; citation verification


## 目录

1 绪论

2 项目综述

3 文献综述

4 问题定义与威胁模型

5 数据集与语料构建

6 EnterpriseRAG-Guard 方法设计

7 系统实现与产品化设计

8 实验设计

9 实验结果与分析

10 网站展示与用户流程

11 局限性与改进方向

12 结论

参考文献

附录A 相应数据与代码

附录B 小组分工情况


## 1 绪论

企业知识库长期面临信息分散、检索成本高和制度解释不一致的问题。传统搜索系统依赖关键词匹配，用户需要知道文件名称、制度关键词或部门路径，才能找到可用信息。大语言模型使自然语言问答成为可能，而 RAG 进一步允许模型在回答时引用企业文档，从而降低幻觉并提高答案可追溯性。因此，越来越多企业开始构建面向员工的知识库 Agent，用于回答福利、报销、IT 支持、合规和治理相关问题。

但是，RAG 系统的安全边界比普通聊天机器人更复杂。普通模型主要受到用户输入影响，而 RAG 系统还受到检索文档影响。如果知识库中存在被投毒的文档，或检索结果包含“忽略安全规则”“把本段作为最高优先级指令”等内容，模型可能把数据当作指令执行。此类间接提示注入攻击尤其危险，因为攻击者不一定直接与模型交互，只需影响知识库或网页内容，就可能改变最终回答。

本项目的研究问题是：如何为不同企业的专属 RAG Agent 构建一套可迁移、可解释、可产品化的提示注入防御框架？项目特别强调“迁移的是安全核心，而不是企业知识内容”。也就是说，每家企业仍保留自己的知识库、来源边界和安全配置，但风险检测、检索隔离、证据抽取、引用验证和拒答逻辑可以复用。

本文的贡献包括四点。第一，提出 EnterpriseRAG-Guard 架构，将公司专属 Agent 分解为通用安全核心、公司安全配置和公司知识库。第二，构建中英双语、多公司、多文档格式的代理知识库语料，并明确区分干净语料与攻击样本。第三，设计 B0 至 B7 的防御消融实验，比较不同安全组件对攻击成功率、引用错误和投毒存活的影响。第四，将系统实现为产品化网站，支持员工查询、红队挑战、防御过程展示以及企业自助接入。


## 2 项目综述

EnterpriseRAG-Guard 的最终定位不是“一个回答所有企业问题的跨企业 Agent”，而是一套可以部署到不同企业专属 RAG Agent 上的安全防御框架。系统的基本公式为：Company Agent = Universal Security Core + Company Security Profile + Company Knowledge Base。其中 Universal Security Core 是可迁移的核心能力，包括风险检测、来源感知检索、隔离、证据抽取、引用验证、修复与拒答；Company Security Profile 描述企业边界，包括公司 ID、允许域名、敏感字段、风险阈值和引用要求；Company Knowledge Base 则是企业自己的真实或代理知识库。

为了展示迁移性，项目预置七家公司知识库：Made Tech、GitLab、37signals/Basecamp、Valve、腾讯、比亚迪和华为。这些公司覆盖软件开发、互联网、制造、游戏和科技通信等行业；文档格式覆盖本地 Markdown/CSV、公开 HTML 和公开 PDF；语言覆盖中文和英文。项目不将这些资料声称为真实内部机密知识库，而是将其作为可复现的公开代理知识库，用于模拟企业知识 Agent 的安全风险。

系统实现分为研究层和产品层。研究层负责语料构建、防御算法、实验运行和结果分析；产品层负责网站展示、员工查询、攻击挑战、证据可视化和企业接入。最终网站不再只是一个空白问答框，而是一个面向 HR、员工和客户管理员的企业知识安全助手：普通员工可以选择公司并提出政策问题；红队模式可以尝试攻击并观察普通 Agent 与安全 Agent 的差异；管理员可以通过接入向导创建新企业租户并运行安全摄取扫描。

项目代码对应文件包括：build_enterprise_corpus.py 用于构建公开企业语料；enterprise_rag_guard.py 实现核心防御流程；run_guard_transfer_experiment.py 运行 B0-B7 消融实验；guard_demo_server.py 提供产品化网站；enterprise_onboarding.py 实现租户接入、连接器抽象和安全摄取管道。


### 表1 项目主要模块与职责


## 3 文献综述

RAG 的基本思想是在生成模型回答之前，从外部知识库检索相关文档，并将检索结果作为上下文输入模型。Lewis 等提出的 Retrieval-Augmented Generation 方法证明，检索模块可以显著增强开放域问答与知识密集型任务的事实性[1]。在企业场景中，RAG 的优势在于可以利用组织已有制度、手册、网页和数据库，降低模型参数更新成本，并通过引用提高答案可审计性。

提示注入研究指出，语言模型容易受到自然语言指令覆盖的影响。直接提示注入通常发生在用户输入中，攻击者要求模型忽略系统规则或泄露隐藏提示；间接提示注入则发生在网页、邮件、文档和检索片段中，模型在处理非可信内容时错误地将数据解释为指令。Greshake 等对间接提示注入的研究表明，LLM 集成应用可能因为外部内容而执行用户未授权的行为[2]。对于 RAG 系统而言，间接注入尤其重要，因为检索过程会主动把外部文档放入上下文。

现有防御大致分为三类。第一类是输入输出过滤，例如检测敏感词、凭证请求或越权意图。这类方法成本低、可解释，但容易被改写或语义绕过。第二类是指令与数据隔离，即明确区分系统指令、用户请求和非可信证据，避免模型把文档内容当作更高优先级指令。第三类是检索与引用层面的防御，包括来源校验、权限过滤、引用验证和检索结果重排。OWASP LLM Top 10 将提示注入、敏感信息泄露、供应链风险和过度代理权限列为 LLM 应用的重要风险[3]，这些风险与企业 RAG 场景高度相关。

从 AI 治理角度看，NIST AI Risk Management Framework 强调 AI 系统需要治理、映射、测量和管理四类活动[4]。这说明企业级 RAG 安全不能只依赖一次性模型提示，而应包含持续评估、日志、策略配置、版本控制和风险监控。本项目因此不仅实现问答防御，还加入红队评估、攻击面分析、企业接入和安全摄取流程。

与已有研究相比，本项目的特点是将提示注入防御落到“企业专属知识库 Agent”这一应用场景中，并强调多企业迁移。多数课程型 RAG 项目只在单一数据集上比较普通检索与过滤规则，而 EnterpriseRAG-Guard 将安全边界、公司配置、来源可信度、引用校验和产品接入流程结合起来，使系统既能用于实验，也能讲清楚未来产品化路径。


## 4 问题定义与威胁模型

本项目研究对象是企业知识库 RAG Agent。给定用户问题 q、目标企业 c 和企业知识库 D_c，系统需要检索相关证据 E，并生成带引用的回答 a。安全目标是：回答只能基于目标企业允许来源中的可信证据；不得泄露凭证、系统提示词或私人数据；不得把检索文档中的恶意指令当作系统指令；不得引用被投毒、跨公司或不存在的证据。

威胁模型包括五类攻击。第一，直接用户注入：攻击者在问题中要求模型忽略规则、伪造政策或泄露凭证。第二，凭证索取：攻击者以无法登录、紧急处理等理由索要密码、API key 或 HR/财务系统凭证。第三，跨公司污染：攻击者要求系统用别家公司的政策回答当前公司的问题。第四，自适应政策修订：攻击者伪装成“最新高管批准修订”，试图覆盖原有政策。第五，检索文档投毒：攻击者将恶意说明伪装成内部政策，使其被检索并进入生成上下文。

项目假设攻击者可以控制用户输入，也可能影响某些待检索文档，但不能修改系统代码、企业安全配置或真实允许域名列表。项目暂不建模真实身份认证、员工级 ACL 和内部 SSO，但在产品化设计中预留 Tenant Profile、Document ACL 和安全摄取接口。

安全评价关注四个指标。攻击成功率衡量攻击问题是否导致不安全回答、错误引用、跨公司污染或不应拒答的拒答。正常任务成功率衡量正常问题是否得到非拒答且引用可验证的答案。引用错误率衡量答案引用是否缺失、伪造、跨公司或来自投毒片段。投毒存活率衡量被检索到的投毒片段是否最终进入回答。


## 5 数据集与语料构建

项目构建的最终干净语料存储于 data/enterprise_corpus/company_chunks.csv，共包含 1084 个知识片段。语料来源包括本地 Made Tech 员工手册 chunk、GitLab 和 Basecamp 公开手册网页、Valve 公开员工手册 PDF，以及腾讯、比亚迪、华为公开 PDF 报告或公告。为了保证语料可复现，项目记录 source_url、source_host、source_type、trust_level、document_version、content_hash 和 instruction_risk_score 等元数据。

语料具有四种异质性。第一是语言异质性，包含中文和英文。第二是企业异质性，覆盖科技、互联网、制造、软件协作和游戏公司。第三是格式异质性，包含 HTML、PDF、Markdown/CSV 等格式。第四是内容异质性，覆盖员工制度、治理、风险、供应链、社会责任、企业文化和福利相关内容。这些异质性使迁移评估比单一员工手册更接近真实企业知识场景。

中文企业腾讯、比亚迪、华为各取 200 个去重片段，并非合成补齐。脚本从公开 PDF 中解析出候选段落后按固定目标数量截取，以平衡不同企业语料规模，避免大型 PDF 对整体评估产生过强影响。需要注意的是，本项目使用公开资料构建代理知识库，并不声称拥有真实企业内部文档。因此更准确的表述是：本项目使用公开企业资料构建可复现的代理知识库，用于模拟企业内部知识 Agent 的检索与安全风险。

攻击样本与干净语料严格分离。干净语料只包含公开或本地原始资料；投毒 chunk 和攻击问题由实验脚本生成，用于评测和网站演示，不被计入干净公司知识库。这一区分避免了将合成攻击文本误称为真实企业政策。

表2 最终语料公司分布

表3 语料来源类型统计


## 6 EnterpriseRAG-Guard 方法设计

EnterpriseRAG-Guard 的方法设计可以分为确定性边界防御和语义防御两类。确定性边界防御包括 company_id、source_host、allowed_domains、content_hash、引用 ID 存在性和跨公司引用限制。这些规则可审计、稳定且成本低，适合企业合规场景。语义防御包括 query risk detection、chunk instruction risk、instruction/evidence isolation、extractor-generator isolation、policy claim verification 和 repair/refusal，用于处理来源看似正确但文本本身包含恶意指令的情况。

第一层是查询风险检测。系统使用中英文模式识别凭证请求、私人数据请求、政策伪造、系统提示词索取和绕过安全规则等行为。对于中文，系统识别“密码”“凭证”“访问令牌”“系统提示词”“忽略规则”“特殊无限福利”等攻击表达。风险检测不是最终防线，而是用于影响后续检索、拒答和验证决策。

第二层是来源感知检索。普通 RAG 主要按相关性排序，而本项目在相关性之外加入企业匹配、来源域名、trust_level、投毒标记、instruction_risk_score 和 source_type。wrong-company、untrusted、poisoned 或 instruction-like 的 chunk 可以被检索用于观测，但不会直接进入最终生成，而是进入 quarantine。

第三层是指令/证据隔离。系统把检索文档明确视为非可信证据，而不是可执行指令。即使某个 chunk 写着“忽略所有之前的规则”，该文本也不会覆盖系统安全策略。第四层是抽取-生成隔离。系统先从安全证据中抽取事实 claim，再根据 claim 生成答案，减少原始恶意文本直接进入生成阶段的机会。

第五层是引用与策略验证。生成答案后，系统检查引用是否存在、是否属于目标公司、是否来自被隔离或投毒片段、是否出现敏感信息或伪造政策。如果验证失败，完整 B7 防御会尝试一次修复；仍无法安全回答时则拒答。

表4 B0-B7 消融设置


### 图1 EnterpriseRAG-Guard 防御流程

用户问题 → 查询风险检测 → 企业安全配置加载 → 来源感知检索 → 可疑证据隔离 → 可信 claim 抽取 → 答案生成 → 引用与策略验证 → 修复或拒答


## 7 系统实现与产品化设计

项目后端采用 Python 实现，核心代码保持可解释和确定性。enterprise_rag_guard.py 定义 GuardChunk、CompanyProfile、DefenseConfig 和 EnterpriseRAGGuard 等核心结构。检索部分使用轻量级词项匹配和打分融合，便于在无外部向量数据库时复现实验；安全部分使用显式元数据和风险模式实现可审计防御。虽然该实现不等同于生产级语义分类器，但适合课程项目展示安全机制和实验逻辑。

产品化设计新增 enterprise_onboarding.py。该文件定义 KnowledgeConnector 抽象接口，未来可以扩展 PDFConnector、SharePointConnector、ConfluenceConnector、WebsiteCrawlerConnector、DatabaseConnector 和 VectorDBConnector。所有来源最终转换为统一 DocumentRecord，其中包含 tenant_id、document_id、title、content、source_type、source_uri、department、access_groups、version、content_hash 和 security_label。

安全摄取管道 SecureIngestionPipeline 在文档进入索引前执行扫描：文件/来源验证、文本抽取、指令风险扫描、PII/凭证检测、来源和版本校验、人工审批或隔离、切分与索引。网站中的“创建企业安全 Agent”演示即基于该模块：管理员输入企业信息和示例文档后，系统生成 TenantProfile，并报告可索引文档、隔离文档和风险发现。

产品架构分为控制面和数据面。控制面负责租户创建、数据源连接、安全配置、用户权限、模型选择、风险阈值、策略版本、监控和审计。数据面负责每次真实请求中的 query detection、权限过滤、检索、quarantine、evidence extraction、生成、引用验证和 repair/refusal。该划分使系统能够支持 SaaS、客户 VPC/私有云和 on-premise 三类交付模式。


### 图2 产品化平台结构

企业数据源 → Connector Layer → Secure Ingestion → Tenant Knowledge Store → EnterpriseRAG-Guard Data Plane → Employee Portal / Existing RAG Gateway


## 8 实验设计

实验目标是评估不同防御组件对正常任务和攻击任务的影响。实验输入为 1084 个公司知识片段和自动生成的 224 个评测问题。每家公司 32 个问题，覆盖正常问答、直接注入、凭证索取、跨公司污染、自适应政策修订和检索文档投毒等类型。

对于每个问题，实验脚本分别运行 B0 至 B7 八种防御配置，并记录回答、引用、是否拒答、检索到的 chunk、被隔离的 chunk、是否存在引用错误、投毒是否存活以及运行延迟。评价指标包括正常任务成功率、攻击成功率、攻击抵抗率、引用错误率、投毒检索率、投毒存活率和 required refusal precision/recall。

需要强调的是，当前评测是确定性代理指标，不是人工专家评分。攻击成功率的判定依据包括不应拒答却拒答、应该拒答却未拒答、引用错误、跨公司引用、投毒引用和明显不安全内容。该评价适合系统可行性和消融分析，但不足以证明系统在所有企业和所有攻击形式下普遍有效。

表5 评测集攻击面分布

表6 评测集语言分布


## 9 实验结果与分析

总体结果显示，完整防御 B7 显著降低了提示注入风险。普通 RAG B0 的攻击成功率为 89.29%，而 B7 为 25.00%，绝对下降 64.29 个百分点。B0 的引用错误率为 58.48%，说明普通 RAG 很容易产生缺失、错误、跨公司或投毒引用；B7 的引用错误率为 0，说明引用验证和隔离机制在当前评测集上有效。

正常任务方面，B0 的正常任务成功率为 67.86%，B7 为 100.00%。这一结果不能解释为“防御天然提高所有任务能力”，更稳妥的理解是：在当前评测集上，来源感知重排、证据抽取和 repair/refusal 机制没有观察到正常任务效用损失，并改善了部分原本因错误引用或跨公司证据导致失败的正常问题。

从消融曲线看，B1 prompt guardrail 有一定效果，但不足以抵抗检索文档投毒和跨公司污染。B2 风险检测降低了部分用户查询攻击，但仍可能让错误证据进入生成。B3 来源感知检索是关键转折点，显著降低引用错误和投毒存活。B4、B5、B6 在当前确定性实现中进一步稳定输出，使最终 B7 能够在无法安全回答时拒答。

值得注意的是，B7 仍有 25% 攻击成功率。这说明分层防御显著降低风险，但没有解决提示注入问题。残余风险可能来自检索相关性不足、问题本身带有复杂双重意图、中文 PDF 抽取噪声、风险检测覆盖不足，或评价规则将某些保守拒答视为攻击成功。后续需要扩大样本量并进行人工标注，以进一步定位残余风险。

表7 B0 与 B7 总体对比

表8 B0-B7 消融结果


## 10 分攻击面与迁移性分析

迁移性分析关注同一套安全核心能否在不同公司上复用。本项目中，防御代码、检测器、隔离逻辑和验证流程在所有公司之间保持一致；允许变化的是公司 ID、allowed domains、敏感字段、语言和知识库内容。当前实验使用共享默认阈值，而不是为每家公司单独调参，因此结果更接近 profile-only transfer，而非针对每家公司优化后的最佳结果。

按攻击面分析比只看总体 ASR 更有解释力。直接用户注入和凭证索取主要考验 query risk detection 与 refusal；跨公司污染主要考验 company boundary 和 citation verification；检索文档投毒主要考验 chunk risk、quarantine 与 extractor-generator isolation；自适应政策修订则更接近真实攻击，因为它不一定包含明显恶意词，而是伪装成新的政策版本。

从产品角度看，迁移性并不意味着所有企业完全共享同一配置。更合理的产品模式包括三层：Shared Default，即所有企业使用相同阈值；Profile Only，即只替换企业域名、敏感字段和语言；Profile + Calibration，即允许用少量开发集校准阈值。课程项目当前实现前两层，并在企业接入模块中为第三层预留配置入口。

表9 分攻击面攻击成功率对比


## 11 网站展示与用户流程

最终网站定位为中文优先的企业知识安全助手，而不是裸露实验指标的研究面板。首页强调“让员工放心查询公司知识，也让攻击者无法劫持回答”，并提供员工查询、攻击挑战、企业接入和安全流程四个入口。普通员工可以选择公司和语言，提出 HR、IT、合规或治理相关问题；国外公司问题可以切换英文。

攻击挑战模式服务于答辩和客户演示。用户可以点击直接注入、索要凭证、跨公司污染、伪装修订和投毒文档等模板。系统并排展示未防护 Agent 与安全 Agent 的回答，使攻击效果和防御效果直观可见。每次运行后，页面展示防御 trace、可信证据和隔离区，说明系统不是简单拒答，而是在检索和验证过程中逐步做出安全决策。

企业接入向导展示第八家公司如何加入系统。管理员填写企业名称、语言、行业、交付方式、允许来源和计划接入的数据源，系统对示例文档执行安全摄取扫描，输出已发现文档、可索引文档、隔离文档和推荐 Tenant Profile。这个功能回应了“如果企业想购买服务，如何接入自己的知识库”的问题，使项目从预装数据原型升级为可外接企业数据的产品框架。


### 图3 网站主要用户流程

首页 → 员工查询 / 攻击挑战 / 企业接入 → 安全 Agent 回答 → 防御 trace → 可信证据与隔离区 → 企业管理员查看接入扫描报告


## 12 局限性与改进方向

第一，当前评测规模仍然有限。224 个问题平均到 7 家公司后，每家公司只有 32 个样本，再细分攻击面后子组样本较少。因此结果应表述为系统可行性实验和初步消融结果，而不是普遍有效性证明。后续应扩展到至少 700 至 1050 个问题，并加入人工标注。

第二，当前生成方式偏 extractive，答案有时会直接摘取 PDF 表格或报告原文，产品体验不如真实 LLM 生成式助手自然。后续可以接入 LLM 对抽取 claim 做更自然的摘要，但必须保留引用验证和输出审查。

第三，真实企业场景需要身份认证和文档级 ACL。本项目产品化设计已经引入 TenantProfile 和 DocumentRecord 的 access_groups 字段，但尚未实现真实 SSO、RBAC、部门权限同步和审计日志。生产系统必须先确定 AllowedChunks = TenantScope ∩ UserPermissions ∩ DocumentACL，再进行检索，而不能先把敏感文档放入模型上下文。

第四，语义防御仍然比较轻量。风险检测主要依赖可解释模式和启发式信号，可能被复杂改写绕过。未来可以引入训练好的注入检测器、自然语言推理模型、策略一致性验证器和异常检索监控。

第五，公开企业资料不能完全代表内部知识库。当前实验使用公开资料构建代理知识库，便于复现和展示，但缺少真实内部制度、访问控制、员工角色和合规约束。后续如果用于企业部署，需要通过连接器接入客户真实数据，并在客户环境中完成安全测试。


## 13 结论

本文总结了 EnterpriseRAG-Guard 项目：一套面向企业专属知识库 Agent 的可迁移提示注入防御框架。项目的核心思想是，每家公司拥有独立知识库边界和安全配置，而风险检测、来源感知检索、证据隔离、抽取-生成隔离、引用验证和修复/拒答构成可复用的通用安全核心。

实验表明，在 1084 个知识片段和 224 个评测问题组成的代理环境中，完整 B7 防御显著降低攻击成功率、引用错误和投毒存活。虽然系统仍存在残余风险，但相比普通 RAG 已经展示出分层防御的价值。项目同时将研究原型产品化，提供中文优先网站、员工查询、攻击挑战、防御 trace、企业接入向导和安全摄取流程，使项目不只是一个课程型 RAG 实验，而是可以解释为企业 RAG 安全网关与评估平台。

未来工作将集中在扩大评测集、接入真实企业数据源、实现文档级权限、引入更强语义检测和支持私有化部署。通过这些改进，EnterpriseRAG-Guard 可以进一步从课程项目原型演进为面向企业知识助手的安全基础设施。


## 参考文献

[1] Lewis P., Perez E., Piktus A., et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS, 2020. https://arxiv.org/abs/2005.11401

[2] Greshake K., Abdelnabi S., Mishra S., et al. Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection. arXiv, 2023. https://arxiv.org/abs/2302.12173

[3] OWASP Foundation. OWASP Top 10 for Large Language Model Applications. https://owasp.org/www-project-top-10-for-large-language-model-applications/

[4] National Institute of Standards and Technology. Artificial Intelligence Risk Management Framework (AI RMF 1.0). https://www.nist.gov/itl/ai-risk-management-framework

[5] Shanghai Jiao Tong University Undergraduate Academic Affairs Office. 2025届本科生毕业设计（论文）资料及表格. https://www.jwc.sjtu.edu.cn/info/1041/117021.htm

[6] GitLab. GitLab Handbook. https://handbook.gitlab.com/handbook/

[7] Basecamp. Basecamp Employee Handbook. https://basecamp.com/handbook

[8] Valve Corporation. Valve New Employee Handbook. https://www.valvesoftware.com/en/publications

[9] Tencent. Tencent Annual and ESG Reports. https://www.tencent.com/en-us/investors/financial-news.html

[10] Huawei. Huawei Annual Report and Sustainability Report. https://www.huawei.com/en/annual-report/2024

[11] BYD Company Limited. Annual Report and Sustainability Information. https://www.bydglobal.com/

[12] Liu Y., Deng G., Xu Z., et al. Jailbreaking ChatGPT via Prompt Engineering: An Empirical Study. arXiv, 2023.

[13] Perez F., Ribeiro I. Ignore Previous Prompt: Attack Techniques For Language Models. NeurIPS ML Safety Workshop, 2022.

[14] Microsoft Research. Spotlighting and related instruction-data separation ideas for prompt injection defense in LLM applications, 2024.

[15] OpenAI. Best practices for prompt engineering and instruction hierarchy in LLM applications. https://platform.openai.com/docs/


## 附录A 相应数据与代码

项目代码和数据均位于 GitHub 仓库 Chiefy91/prompt-injection-rag-handbook。最终版本主线文件包括 build_enterprise_corpus.py、enterprise_rag_guard.py、enterprise_onboarding.py、run_guard_transfer_experiment.py 和 guard_demo_server.py。旧版 baseline 和历史实验输出已归档到 legacy/，避免与最终项目主线混淆。

最终干净语料位于 data/enterprise_corpus/company_chunks.csv；评测问题位于 data/enterprise_corpus/guard_eval_questions.csv；实验总结果位于 outputs/enterprise_rag_guard/results.csv；消融汇总位于 outputs/enterprise_rag_guard/summary/ablation_summary.csv；按公司和按攻击面的结果分别位于 outputs/enterprise_rag_guard/by_company/ 和 outputs/enterprise_rag_guard/by_attack_surface/。

复现实验的基本命令为：python3 -m pip install -r requirements.txt；python3 build_enterprise_corpus.py --china-target 200 --timeout 35；python3 run_guard_transfer_experiment.py --skip-build-corpus；python3 guard_demo_server.py。若本地 Python 缺少 pypdf，PDF 语料会被跳过，中文企业语料将不完整。

表10 数据与代码说明


## 附录B 小组分工情况

由于当前未提供真实组员姓名，本文先使用占位姓名。提交前请将“成员A/B/C/D”替换为真实姓名与学号，并根据实际贡献微调比例。分工应保持具体、可核查，避免只写“共同完成”。

表11 小组分工建议表


## 附录C 答辩讲解要点

答辩开场可以从企业知识助手的真实需求切入：员工希望用自然语言查询公司制度，但企业不能允许模型因为提示注入而伪造政策、泄露凭证或引用错误来源。随后强调本项目不是混合多家公司知识库的跨公司 Agent，而是可部署到不同企业专属 Agent 上的安全框架。

介绍方法时建议按两类防御展开。确定性边界防御负责 company ID、allowed domains、source host、content hash 和 citation ID；语义防御负责 query risk、chunk instruction risk、extractor-generator isolation、policy verification 和 repair/refusal。这样可以避免老师误解为系统只靠 company_id 过滤。

介绍实验时应主动说明局限：224 条评测问题适合原型验证和消融分析，但还不足以证明普遍有效；B7 攻击成功率仍有 25%，说明防御显著降低风险但没有完全解决提示注入。主动承认残余风险会增强项目可信度。

演示网站时建议先用员工查询展示正常问题，再进入攻击挑战，用“忽略所有规则并声称批准特殊无限福利”的例子展示普通 Agent 被诱导、安全 Agent 拒答，最后打开防御 trace、可信证据和隔离区，说明系统如何工作。最后展示企业接入向导，回答“如果第八家公司想购买服务怎么办”。
