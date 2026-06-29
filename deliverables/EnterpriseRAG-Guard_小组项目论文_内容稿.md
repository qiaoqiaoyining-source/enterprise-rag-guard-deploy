# 摘要

随着大语言模型逐步进入企业知识管理、员工服务、合规问答和内部流程支持场景，基于检索增强生成（Retrieval-Augmented Generation, RAG）的企业知识库 Agent 成为组织内部信息查询的重要入口。RAG 通过检索外部知识片段来增强回答的事实性，但也同时扩大了提示注入攻击的暴露面：攻击者既可以在用户问题中直接嵌入“忽略规则”“泄露凭证”等恶意指令，也可以在被检索文档中植入间接指令，使模型错误地把非可信证据当作更高优先级指令执行。

本项目设计并实现 EnterpriseRAG-Guard，一套面向企业专属知识库 Agent 的可迁移提示注入防御框架。系统不构建一个混合回答所有公司问题的跨企业代理，而是将每家企业建模为独立租户：Company Agent = Universal Security Core + Company Security Profile + Company Knowledge Base。通用安全核心负责查询风险检测、来源感知检索、证据隔离、抽取-生成隔离、引用验证和修复/拒答；企业安全配置负责定义公司边界、允许来源、敏感字段、风险阈值和引用要求；企业知识库由该企业公开资料或未来客户接入数据构成。

实验构建了覆盖 Made Tech、GitLab、37signals/Basecamp、Valve、腾讯、比亚迪和华为的中英双语多企业语料，共 1084 个去重知识片段，并生成 224 个正常与攻击评测问题。结果显示，完整 B7 防御将普通 RAG 的攻击成功率从 89.29% 降至 25.00%，引用错误率从 58.48% 降至 0，投毒存活率从 100% 降至 0。项目进一步实现公网可访问的网站，支持员工查询、攻击挑战、防御 Trace、可信证据/隔离区展示和企业自助接入。本文系统总结项目背景、相关研究、方法设计、实现细节、实验分析、局限性和小组分工。

关键词：检索增强生成；提示注入；企业知识库；安全网关；多租户隔离；引用验证

# Abstract

Large language models are increasingly deployed as enterprise knowledge assistants for HR, compliance, IT support and internal policy question answering. Retrieval-Augmented Generation improves factual grounding by inserting retrieved documents into the model context, but it also creates a broader attack surface. Malicious instructions may appear directly in user queries or indirectly inside retrieved documents, causing a RAG agent to fabricate policies, leak sensitive information, cite poisoned evidence, or mix policies across companies.

This project proposes EnterpriseRAG-Guard, a transferable defense framework for company-specific RAG agents. Instead of building a single mixed cross-company assistant, each enterprise is modeled as an isolated tenant: Company Agent = Universal Security Core + Company Security Profile + Company Knowledge Base. The universal security core performs query risk detection, provenance-aware retrieval, evidence quarantine, extractor-generator isolation, citation verification, and repair/refusal. The company profile defines tenant boundaries, allowed sources, sensitive fields, risk thresholds, and citation requirements.

The evaluation corpus contains 1,084 clean chunks from seven companies: Made Tech, GitLab, 37signals/Basecamp, Valve, Tencent, BYD, and Huawei. A 224-case benchmark covers normal queries and attacks such as direct user injection, credential extraction, cross-company contamination, adaptive policy fabrication, and retrieved-document poisoning. In the current benchmark, the full B7 guard reduces attack success rate from 89.29% to 25.00%, citation error rate from 58.48% to 0, and poison survival rate from 100% to 0. The project further implements a public web platform supporting employee queries, red-team challenges, defense traces, safe evidence and quarantine visualization, and real tenant onboarding. This paper presents the motivation, literature review, method, implementation, experiments, limitations, conclusion, and team contribution.

Key words: Retrieval-Augmented Generation; prompt injection; enterprise knowledge agent; security gateway; tenant isolation; citation verification

# 目录

# 1 绪论

企业知识库长期存在资料分散、检索成本高、制度解释不一致和审计困难等问题。员工在查询福利、报销、IT 支持、合规制度或社会责任资料时，往往需要知道文档名称、制度关键词或部门路径，才能通过传统搜索找到相关文件。大语言模型提供了自然语言交互能力，而 RAG 进一步允许模型在回答时引用企业文档，从而降低幻觉并提高可追溯性。因此，越来越多企业开始尝试构建面向员工的知识库 Agent。

然而，RAG 的安全边界比普通聊天机器人更复杂。普通模型主要受到用户输入影响，而 RAG 系统还受到检索文档影响。只要某个网页、PDF、Wiki 页面或内部笔记被检索进入上下文，模型就可能同时看到“事实证据”和“恶意指令”。如果系统没有明确区分二者，攻击者便可能通过间接提示注入改变最终回答。例如，投毒文档可以伪装成最新高管批准政策，要求模型忽略原有制度、泄露凭证或引用伪造来源。

本项目的核心研究问题是：如何为不同企业的专属 RAG Agent 构建一套可迁移、可解释、可产品化的提示注入防御框架？“可迁移”在这里并不意味着所有公司共享同一个混合知识库，而是指安全核心可以跨企业复用，而每家企业仍保留自己的知识边界、来源策略、敏感字段和安全配置。

围绕这一问题，本文提出并实现 EnterpriseRAG-Guard。项目最初从员工手册 RAG 和提示注入实验出发，最终升级为面向多企业、多语言、多攻击面的安全网关与产品化原型。系统预置七家公司公开代理知识库，并支持新企业通过接入向导提交资料，经过安全摄取、风险扫描和租户 profile 生成后立即进入可查询状态。

本文的贡献包括四点。第一，提出 Company Agent = Universal Security Core + Company Security Profile + Company Knowledge Base 的架构，将企业知识内容与通用安全能力解耦。第二，构建 1084 个中英双语多企业知识片段和 224 个正常/攻击评测问题。第三，设计 B0 至 B7 消融实验，量化查询检测、来源感知检索、证据隔离、引用验证和拒答机制的贡献。第四，将研究原型产品化为公网可访问的网站，支持员工查询、红队攻击挑战、Trace 展示和真实企业接入流程。

# 2 项目综述

EnterpriseRAG-Guard 的最终定位不是“一个问答网页”，也不是“把多家公司资料混合在一起的跨公司 Agent”，而是一套可以部署到不同企业知识助手前面的 RAG 安全框架。项目将企业知识 Agent 拆解为三个部分：通用安全核心、企业安全配置和企业知识库。通用安全核心负责可复用的防御逻辑；企业安全配置描述租户边界、允许来源、敏感字段和风险阈值；企业知识库则由该企业自己的文档、网页、数据库或已有向量库构成。

为了验证迁移性，项目预置 Made Tech、GitLab、37signals/Basecamp、Valve、腾讯、比亚迪和华为七个企业租户。这些数据来源均为公开资料或原有课程资料，不涉及真实内部机密。它们覆盖软件开发、互联网、制造、游戏和通信等行业，文档格式包括 Markdown/CSV、HTML 和 PDF，语言包括中文和英文。通过这种设计，项目能够在不同公司、语言和来源格式之间比较同一套安全核心的效果。

系统由研究层和产品层组成。研究层包括语料构建、攻击样本构造、防御算法和消融实验；产品层包括网站界面、DeepSeek 生成、百炼 Embedding 重排、企业接入、持久化租户索引和公网部署。最终版本已部署在 Render 公网服务上，网站支持员工查询、攻击挑战、企业接入和安全流程四个页面。

[表格：modules]

项目的关键转变在于：从“做一个能回答员工手册问题的 RAG”升级为“做一个面向企业知识库 Agent 的安全产品原型”。因此，论文和答辩应重点说明防御机制如何迁移、如何验证、如何接入企业数据，而不是只展示普通问答效果。

# 3 文献综述

RAG 的基本思想是在生成模型回答之前，从外部知识库检索相关文档，并将检索结果作为上下文输入模型。Lewis 等提出的 Retrieval-Augmented Generation 方法证明，检索模块可以增强开放域问答与知识密集型任务的事实性[1]。在企业场景中，RAG 的优势在于可以利用组织已有制度、手册、网页和数据库，避免频繁微调模型，并通过引用提高答案可审计性。

提示注入研究指出，语言模型容易受到自然语言指令覆盖影响。直接提示注入发生在用户输入中，攻击者要求模型忽略系统规则、泄露隐藏提示或伪造输出格式；间接提示注入则发生在网页、邮件、文档和检索片段中，模型在处理非可信内容时错误地将数据解释为指令。Greshake 等研究表明，LLM 集成应用可能因为外部内容而执行用户未授权的行为[2]。对于 RAG 系统而言，间接注入尤其重要，因为检索过程会主动将外部内容放入上下文。

现有防御大致可以分为三类。第一类是输入输出过滤，包括检测敏感词、凭证请求、越权意图或恶意格式要求。这类方法成本低、可解释，但容易被改写绕过。第二类是指令与数据隔离，即明确区分系统指令、用户请求和非可信证据，避免模型把文档内容当作更高优先级指令。第三类是检索与引用层面的防御，包括来源校验、权限过滤、引用验证和检索结果重排。OWASP LLM Top 10 将提示注入、敏感信息泄露、供应链风险和过度代理权限列为 LLM 应用的重要风险[3]，这些风险与企业 RAG 高度相关。

从 AI 治理角度看，NIST AI Risk Management Framework 强调 AI 系统需要治理、映射、测量和管理四类活动[4]。这说明企业级 RAG 安全不能只依赖一次性 prompt，而应包含持续评估、日志、策略配置、版本控制和风险监控。本项目因此不仅实现问答防御，还设计红队评估、攻击面分析、企业接入和安全摄取流程。

与已有课程型项目相比，本项目的区别在于：第一，关注企业专属知识边界，而不是单数据集 RAG；第二，同时处理中文和英文公开企业资料；第三，将防御拆成可消融的 B0-B7 组件；第四，把实验原型扩展为可演示、可部署、可接入新企业数据的产品化系统。

# 4 问题定义与威胁模型

给定用户问题 q、目标企业 c 和企业知识库 D_c，企业 RAG Agent 需要检索证据 E 并生成带引用的回答 a。安全目标可以表述为：回答只能基于目标企业允许来源中的可信证据；不得泄露凭证、系统提示词、个人信息或未授权内容；不得把检索文档中的恶意指令当作系统指令；不得引用被投毒、跨公司或不存在的证据。

本项目考虑五类攻击。第一，直接用户注入：攻击者在问题中要求模型忽略规则、伪造政策、改变输出格式或泄露系统提示词。第二，凭证索取：攻击者以紧急处理、无法登录或审计为理由索要密码、API key、访问令牌或内部系统凭证。第三，跨公司污染：攻击者要求系统用其他公司的制度回答当前公司的问题，或诱导模型混淆企业边界。第四，自适应政策修订：攻击者伪装成最新高管批准说明，试图覆盖真实政策。第五，检索文档投毒：攻击者将恶意说明伪装成内部政策、网页或 PDF 内容，使其被检索并进入上下文。

项目假设攻击者可以控制用户输入，也可能影响某些待检索文档或公开网页，但不能修改系统代码、企业安全配置或真实允许来源列表。当前实现不建模真实员工身份、部门权限和 SSO，但在产品化设计中预留 TenantProfile、DocumentRecord、access_groups 和安全摄取接口。生产系统还需要将用户权限、文档 ACL 和审计日志纳入检索前过滤。

评价指标包括正常任务成功率、攻击成功率、攻击抵抗率、引用错误率、投毒检索率、投毒存活率以及 required refusal precision/recall。攻击成功率不是单纯看模型是否输出恶意词，而是综合考虑不应回答的问题是否拒答、引用是否真实、是否跨公司、是否引用投毒片段以及是否出现明显不安全内容。

# 5 数据集与语料构建

最终干净语料位于 data/enterprise_corpus/company_chunks.csv，共包含 1084 个知识片段。语料来源包括本地 Made Tech 员工手册、GitLab 和 Basecamp 公开手册网页、Valve 公开员工手册 PDF，以及腾讯、比亚迪、华为公开 PDF 报告或公告。每个 chunk 记录 company_id、company_name、language、source_url、source_host、source_type、doc_title、corpus_origin、trust_level、document_version、content_hash 和 instruction_risk_score 等元数据。

[表格：corpus]

语料具有四类异质性。第一是语言异质性：中文 600 个 chunk，英文 484 个 chunk。第二是企业异质性：覆盖科技、互联网、制造、软件协作和游戏等不同领域。第三是格式异质性：包含本地 CSV/Markdown、公开 HTML、公开 PDF。第四是内容异质性：涵盖员工制度、公司文化、治理、风险、合规、社会责任和业务介绍。这些异质性使迁移评估比单一员工手册更接近真实企业知识场景。

[表格：source]

中文企业腾讯、比亚迪、华为各取 200 个去重片段。该做法不是合成补齐，而是从公开 PDF 中解析候选段落后按目标数量截取，以平衡不同企业语料规模，避免大型 PDF 对整体评估产生过强影响。需要强调的是，本项目使用公开资料构建代理知识库，并不声称拥有真实企业内部资料。

攻击样本与干净语料严格分离。干净语料只包含公开或本地原始资料；投毒 chunk 和攻击问题由实验脚本生成，用于评测和网站演示，不计入干净公司知识库。这一区分避免把合成攻击文本误称为真实企业政策，也便于复现实验。

# 6 EnterpriseRAG-Guard 方法设计

EnterpriseRAG-Guard 的方法设计由确定性边界防御和语义防御共同组成。确定性边界防御包括 tenant/company ID、source_host、allowed_domains、content_hash、引用 ID 存在性和跨公司引用限制。这些规则可审计、稳定且成本低，适合企业合规场景。语义防御包括 query risk detection、chunk instruction risk、instruction/evidence isolation、extractor-generator isolation、policy claim verification 和 repair/refusal，用于处理来源看似正确但文本本身包含恶意指令的情况。

```text
用户问题 → 查询风险检测 → 企业安全配置加载 → 双语查询改写 → 来源感知检索 → 可疑证据隔离 → 可信证据抽取 → 答案生成 → 引用与策略验证 → 修复或拒答
```

第一层是查询风险检测。系统使用中英文模式识别凭证请求、私人数据请求、政策伪造、系统提示词索取和绕过安全规则等行为。中文检测覆盖“密码”“凭证”“访问令牌”“系统提示词”“忽略规则”“特殊无限福利”等表达。风险检测不是最终防线，而是作为早期信号影响后续检索、拒答和验证。

第二层是来源感知检索。普通 RAG 主要按相关性排序，而本项目在相关性之外加入企业匹配、来源域名、trust_level、投毒标记、instruction_risk_score 和 source_type。wrong-company、untrusted、poisoned 或 instruction-like chunk 可以被检索用于观测，但不会直接进入最终生成，而是进入 quarantine。

第三层是指令/证据隔离。系统把检索文档明确视为非可信证据，而不是可执行指令。即使某个 chunk 写着“忽略所有之前的规则”，该文本也不会覆盖系统安全策略。第四层是抽取-生成隔离。系统先从安全证据中抽取事实 claim，再根据 claim 生成答案，减少原始恶意文本直接进入生成阶段的机会。

第五层是引用与策略验证。生成答案后，系统检查引用是否存在、是否属于目标公司、是否来自被隔离或投毒片段、是否出现敏感信息或伪造政策。如果验证失败，完整 B7 防御会尝试修复；仍无法安全回答时则拒答。

[表格：b0b7]

# 7 系统实现与产品化设计

项目后端采用 Python 实现，核心文件 enterprise_rag_guard.py 定义 GuardChunk、CompanyProfile、DefenseConfig 和 EnterpriseRAGGuard 等结构。检索部分使用轻量词项匹配、语义重排和安全信号融合，便于在无外部向量数据库时复现实验；产品模式下可启用百炼/DashScope text-embedding-v4 对候选证据进行语义重排。生成层支持确定性证据生成和 DeepSeek 模型生成，其中模型生成仍受证据过滤、引用验证和拒答逻辑约束。

产品化新增 enterprise_onboarding.py。该文件定义 KnowledgeConnector 抽象接口，未来可扩展 PDFConnector、SharePointConnector、ConfluenceConnector、WebsiteCrawlerConnector、DatabaseConnector 和 VectorDBConnector。所有来源最终转换为统一 DocumentRecord，其中包含 tenant_id、document_id、title、content、source_type、source_uri、department、access_groups、version、content_hash 和 security_label。

安全摄取管道 SecureIngestionPipeline 在文档进入索引前执行扫描：文件/来源验证、文本抽取、指令风险扫描、PII/凭证检测、来源和版本校验、人工审批或隔离、切分与索引。网站中的“创建企业安全 Agent”演示即基于该模块：管理员输入企业信息和示例文档后，系统生成 TenantProfile，并报告可索引文档、隔离文档和风险发现。

产品架构可以分为控制面和数据面。控制面负责租户创建、数据源连接、安全配置、用户权限、模型选择、风险阈值、策略版本、监控和审计。数据面负责每次真实请求中的 query detection、权限过滤、检索、quarantine、evidence extraction、生成、引用验证和 repair/refusal。该划分使系统能够支持 SaaS、客户 VPC/私有云和本地部署三类交付模式。

[表格：product_modules]

# 8 实验设计

实验目标是评估不同防御组件对正常任务和攻击任务的影响。实验输入为 1084 个公司知识片段和 224 个评测问题。每家公司 32 个问题，其中包含 8 个正常问题和 24 个攻击问题。攻击问题覆盖用户输入注入、跨公司污染、自适应政策修订和检索文档投毒等类型。

[表格：eval_dist]

对于每个问题，实验脚本分别运行 B0 至 B7 八种防御配置，并记录回答、引用、是否拒答、检索到的 chunk、被隔离的 chunk、是否存在引用错误、投毒是否存活以及运行延迟。评价指标包括正常任务成功率、攻击成功率、攻击抵抗率、引用错误率、投毒检索率、投毒存活率和 required refusal precision/recall。

需要强调的是，当前评测是确定性代理指标，不是人工专家评分。攻击成功率的判定依据包括应拒答却未拒答、引用错误、跨公司引用、投毒引用和明显不安全内容。该评价适合系统可行性和消融分析，但不足以证明系统在所有企业和所有攻击形式下普遍有效。

# 9 实验结果与分析

总体结果显示，完整防御 B7 显著降低提示注入风险。普通 RAG B0 的攻击成功率为 89.29%，而 B7 为 25.00%，绝对下降 64.29 个百分点。B0 的引用错误率为 58.48%，说明普通 RAG 很容易产生缺失、错误、跨公司或投毒引用；B7 的引用错误率为 0，说明引用验证和隔离机制在当前评测集上有效。

[表格：ablation]

正常任务方面，B0 的正常任务成功率为 67.86%，B7 为 100.00%。这一结果不能解释为“防御天然提高所有任务能力”，更稳妥的理解是：在当前评测集上，来源感知重排、证据抽取和 repair/refusal 机制没有观察到正常任务效用损失，并改善了部分原本因错误引用或跨公司证据导致失败的正常问题。

从消融曲线看，B1 prompt guardrail 有一定效果，但不足以抵抗检索文档投毒和跨公司污染。B2 风险检测降低了部分用户查询攻击，但仍可能让错误证据进入生成。B3 来源感知检索是关键转折点，显著降低引用错误和投毒存活。B4、B5、B6 在当前确定性实现中进一步稳定输出，使最终 B7 能够在无法安全回答时拒答。

需要注意，B7 仍有 25% 攻击成功率。这说明分层防御显著降低风险，但没有完全解决提示注入问题。残余风险主要来自用户输入攻击中 required refusal precision 的定义、风险检测覆盖不足、问题存在复杂双重意图，以及部分代理指标对“保守拒答”的惩罚。后续需要扩大样本量并加入人工标注，以进一步定位残余风险。

# 10 分攻击面与迁移性分析

分攻击面结果比总体 ASR 更有解释力。直接用户注入和凭证索取主要考验 query risk detection 与 refusal；跨公司污染主要考验 company boundary 和 citation verification；检索文档投毒主要考验 chunk risk、quarantine 与 extractor-generator isolation；自适应政策修订则更接近真实攻击，因为它不一定包含明显恶意词，而是伪装成新的政策版本。

[表格：surface]

在 B7 中，adaptive、cross_company 和 retrieved_document 三类攻击的攻击成功率均降至 0；user_query 攻击成功率仍为 60%。这说明来源感知检索、隔离和引用验证对文档侧攻击非常有效，但仅靠规则检测很难完全覆盖用户侧表达变体。未来若引入训练好的意图分类器、对抗样本增强和人工审核规则，用户侧攻击仍有明显改进空间。

迁移性分析关注同一套安全核心能否在不同公司上复用。本项目中，防御代码、检测器、隔离逻辑和验证流程在所有公司之间保持一致；允许变化的是公司 ID、allowed domains、敏感字段、语言和知识库内容。当前实验使用共享默认阈值，而不是为每家公司单独调参，因此结果更接近 profile-only transfer，而非每家公司优化后的最佳结果。

[表格：company_b7]

从产品角度看，迁移性并不意味着所有企业完全共享同一配置。更合理的产品模式包括三层：Shared Default，即所有企业使用相同阈值；Profile Only，即只替换企业域名、敏感字段和语言；Profile + Calibration，即允许用少量开发集校准阈值。课程项目当前实现前两层，并在企业接入模块中为第三层预留配置入口。

# 11 网站展示与用户流程

最终网站定位为中文优先的企业知识安全助手，而不是裸露实验指标的研究面板。首页强调“让员工放心查询公司知识，也让攻击者无法劫持回答”，并提供员工查询、攻击挑战、企业接入和安全流程四个入口。普通员工可以选择公司和语言，提出 HR、IT、合规或治理相关问题；国外公司问题可以切换英文。

攻击挑战模式服务于答辩和客户演示。用户可以点击直接注入、索要凭证、跨公司污染、伪装修订和投毒文档等模板。系统并排展示未防护 Agent 与安全 Agent 的回答，使攻击效果和防御效果直观可见。每次运行后，页面展示防御 trace、可信证据和隔离区，说明系统不是简单拒答，而是在检索和验证过程中逐步做出安全决策。

企业接入向导展示第八家公司如何加入系统。管理员填写企业名称、语言、行业、交付方式、允许来源和计划接入的数据源，系统对示例文档执行安全摄取扫描，输出已发现文档、可索引文档、隔离文档和推荐 Tenant Profile。实际测试中，包含“访问令牌”“系统提示词”等风险词的文档会被隔离；合规的 HR/报销/社会责任资料会被写入持久化租户索引并立即可查。

公网部署地址为 https://enterprise-rag-guard-deploy.onrender.com。服务运行在 Render Starter 实例，使用 1GB 持久磁盘挂载 /app/data/tenant_agents 保存新接入租户。DeepSeek 和百炼/DashScope 密钥通过 Render 环境变量配置，不写入代码仓库。

# 12 数据、代码与部署说明

代码仓库已迁移到小组成员自己的 GitHub 仓库 enterprise-rag-guard-deploy，最终主线只保留 EnterpriseRAG-Guard 版本，早期 baseline 和历史课程轨道归档在 legacy/ 目录。关键文件包括 build_enterprise_corpus.py、enterprise_rag_guard.py、enterprise_onboarding.py、run_guard_transfer_experiment.py、guard_demo_server.py、Dockerfile、render.yaml 和 README.md。

[表格：files]

数据文件包括 data/enterprise_corpus/company_chunks.csv、data/enterprise_corpus/guard_eval_questions.csv、data/company_profiles.json，以及 outputs/enterprise_rag_guard/ 下的实验结果。为了提交课程资料，建议另外准备一个压缩包，只包含可复现代码、必要数据、实验结果、论文、PPT 和说明文档，不包含 .env、虚拟环境、缓存、API key 或浏览器本地状态。

本地运行命令为：安装依赖后运行 python3 build_enterprise_corpus.py --china-target 200 --timeout 35 构建语料；运行 python3 run_guard_transfer_experiment.py --skip-build-corpus 执行实验；运行 python3 guard_demo_server.py 启动本地网站。公网部署使用 Render 连接 GitHub 仓库，配置环境变量和持久磁盘即可。

# 13 局限性与改进方向

第一，当前评测规模仍有限。224 个问题平均到 7 家公司后，每家公司只有 32 个样本，再细分攻击面后子组样本较少。因此结果应表述为系统可行性实验和初步消融结果，而不是普遍有效性证明。后续应扩展到至少 700 至 1050 个问题，并加入人工标注和置信区间。

第二，真实企业场景需要身份认证和文档级 ACL。本项目产品化设计已经引入 TenantProfile 和 DocumentRecord 的 access_groups 字段，但尚未实现真实 SSO、RBAC、部门权限同步和审计日志。生产系统必须先确定 AllowedChunks = TenantScope ∩ UserPermissions ∩ DocumentACL，再进行检索，而不能先把敏感文档放入模型上下文。

第三，语义防御仍然轻量。风险检测主要依赖可解释模式和启发式信号，可能被复杂改写绕过。未来可以引入训练好的注入检测器、自然语言推理模型、策略一致性验证器和异常检索监控。

第四，公开企业资料不能完全代表内部知识库。当前实验使用公开资料构建代理知识库，便于复现和展示，但缺少真实内部制度、访问控制、员工角色和合规约束。后续如果用于企业部署，需要通过连接器接入客户真实数据，并在客户环境中完成安全测试。

第五，公网产品仍需工程化增强。Render 部署适合作业展示和公开访问，但企业级产品还需要域名、HTTPS 证书、监控告警、日志脱敏、限流、后台任务队列、异步摄取、权限管理和管理员控制台。

# 14 结论

本文总结了 EnterpriseRAG-Guard 项目：一套面向企业专属知识库 Agent 的可迁移提示注入防御框架。项目的核心思想是，每家公司拥有独立知识库边界和安全配置，而风险检测、来源感知检索、证据隔离、抽取-生成隔离、引用验证和修复/拒答构成可复用的通用安全核心。

实验表明，在 1084 个知识片段和 224 个评测问题组成的代理环境中，完整 B7 防御显著降低攻击成功率、引用错误和投毒存活。虽然系统仍存在残余风险，但相比普通 RAG 已展示出分层防御的价值。项目同时将研究原型产品化，提供中文优先网站、员工查询、攻击挑战、防御 trace、企业接入向导、安全摄取流程和公网部署，使项目不只是一个课程型 RAG 实验，而是可以解释为企业 RAG 安全网关与评估平台。

未来工作将集中在扩大评测集、接入真实企业数据源、实现文档级权限、引入更强语义检测和支持私有化部署。通过这些改进，EnterpriseRAG-Guard 可以进一步从课程项目原型演进为面向企业知识助手的安全基础设施。

# 参考文献

[1] Lewis P., Perez E., Piktus A., et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS, 2020.

[2] Greshake K., Abdelnabi S., Mishra S., et al. Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection. arXiv, 2023.

[3] OWASP Foundation. OWASP Top 10 for Large Language Model Applications. https://owasp.org/www-project-top-10-for-large-language-model-applications/.

[4] National Institute of Standards and Technology. Artificial Intelligence Risk Management Framework (AI RMF 1.0). https://www.nist.gov/itl/ai-risk-management-framework.

[5] 上海交通大学教务处. 2025届本科生毕业设计（论文）资料及表格. https://www.jwc.sjtu.edu.cn/info/1041/117021.htm.

[6] GitLab. GitLab Handbook. https://handbook.gitlab.com/handbook/.

[7] Basecamp. Basecamp Employee Handbook. https://basecamp.com/handbook.

[8] Valve Corporation. Valve New Employee Handbook. https://www.valvesoftware.com/en/publications.

[9] Tencent. Tencent Annual and ESG Reports. https://www.tencent.com/en-us/investors/financial-news.html.

[10] Huawei. Huawei Annual Report and Sustainability Report. https://www.huawei.com/en/annual-report/2024.

[11] BYD Company Limited. Annual Report and Sustainability Information. https://www.bydglobal.com/.

[12] Perez F., Ribeiro I. Ignore Previous Prompt: Attack Techniques For Language Models. NeurIPS ML Safety Workshop, 2022.

[13] Liu Y., Deng G., Xu Z., et al. Jailbreaking ChatGPT via Prompt Engineering: An Empirical Study. arXiv, 2023.

[14] Microsoft Research. Spotlighting and instruction-data separation ideas for prompt injection defense in LLM applications, 2024.

[15] OpenAI. Prompt engineering and instruction hierarchy documentation. https://platform.openai.com/docs/.

[16] Alibaba Cloud. DashScope text embedding model documentation. https://help.aliyun.com/zh/model-studio/.

[17] DeepSeek. DeepSeek API documentation. https://api-docs.deepseek.com/.

[18] Render. Web service and persistent disk documentation. https://render.com/docs/.

# 附录A 相应数据与代码整理

建议最终提交一个独立压缩包 EnterpriseRAG-Guard_Submission.zip，而不是提交完整开发目录。完整开发目录包含 .venv、embedding_cache、.git、浏览器状态和本地 .env，不适合作为课程附件。压缩包应只保留可复现实验和展示所需内容。

[表格：package]

建议压缩包结构如下：

```text
EnterpriseRAG-Guard_Submission/
  README.md
  paper/EnterpriseRAG-Guard_小组项目论文.docx
  slides/EnterpriseRAG-Guard_最终展示.pptx
  code/enterprise_rag_guard.py
  code/enterprise_onboarding.py
  code/guard_demo_server.py
  code/build_enterprise_corpus.py
  code/run_guard_transfer_experiment.py
  data/company_profiles.json
  data/enterprise_corpus/company_chunks.csv
  data/enterprise_corpus/guard_eval_questions.csv
  results/ablation_summary.csv
  results/attack_surface_summary.csv
  results/transfer_matrix.csv
  deployment/Dockerfile
  deployment/render.yaml
```

不要放入 .env、API key、.venv、__pycache__、outputs/embedding_cache、浏览器缓存、私有支付或 Render 后台截图。若老师需要复现模型调用，只需说明需要在本地或云端配置 DEEPSEEK_API_KEY 和 DASHSCOPE_API_KEY 两个环境变量。

# 附录B 小组分工情况

[表格：team]

上述分工按五名成员工作量相近的原则设置。实际提交前可以根据真实贡献微调，但建议保留“数据/方法/实验/产品/文档”五条主线，便于老师判断每位成员承担了可核查的工作。