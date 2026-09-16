from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NoticeField:
    key: str
    label: str
    required: bool = True
    placeholder: str = ""


@dataclass(frozen=True)
class NoticeTypeSpec:
    key: str
    title: str
    # A real, correctly-named statute this notice type is commonly issued
    # under - factual naming only (the Act exists and is spelled/dated
    # correctly). Never a substitute for legal advice on which section
    # actually applies to a specific case; left None where the applicable
    # law genuinely varies too much to name one Act responsibly (e.g.
    # divorce, governed by different personal laws depending on the
    # parties' religion/the law they married under).
    statute_reference: str | None
    fields: tuple[NoticeField, ...] = field(default_factory=tuple)


NOTICE_TYPES: dict[str, NoticeTypeSpec] = {
    spec.key: spec
    for spec in [
        NoticeTypeSpec(
            key="STATUTORY_NOTICE", title="Statutory Notice", statute_reference=None,
            fields=(
                NoticeField("statute_name", "Statute/Act this notice is issued under"),
                NoticeField("section_reference", "Section(s) relied upon"),
            ),
        ),
        NoticeTypeSpec(
            key="BREACH_OF_CONTRACT", title="Legal Notice for Breach of Contract", statute_reference=None,
            fields=(
                NoticeField("contract_date", "Date of contract/agreement"),
                NoticeField("contract_description", "Brief description of the contract"),
                NoticeField("relief_sought", "Relief/compensation sought"),
            ),
        ),
        NoticeTypeSpec(
            key="EVICTION_NOTICE", title="Eviction Notice", statute_reference=None,
            fields=(
                NoticeField("property_address", "Property address"),
                NoticeField("tenancy_start_date", "Date tenancy commenced"),
                NoticeField("notice_period_days", "Notice period given (days)"),
                NoticeField("vacate_by_date", "Vacate by date"),
            ),
        ),
        NoticeTypeSpec(
            key="NOTICE_TO_PAY_RENT", title="Notice to Pay Due Rent", statute_reference=None,
            fields=(
                NoticeField("property_address", "Property address"),
                NoticeField("rent_period_from", "Rent due period - from"),
                NoticeField("rent_period_to", "Rent due period - to"),
                NoticeField("rent_amount_due", "Amount of rent due"),
                NoticeField("payment_deadline_date", "Payment deadline"),
            ),
        ),
        NoticeTypeSpec(
            key="DEFAMATION_NOTICE", title="Defamation Notice", statute_reference=None,
            fields=(
                NoticeField("publication_details", "Where/when the statement was published or made"),
                NoticeField("demand_amount", "Damages demanded (if any)", required=False),
                NoticeField("retraction_deadline_date", "Deadline for retraction/apology"),
            ),
        ),
        NoticeTypeSpec(
            key="CHEQUE_BOUNCE_NOTICE", title="Cheque Bounce Notice",
            statute_reference="Section 138, Negotiable Instruments Act, 1881",
            fields=(
                NoticeField("cheque_number", "Cheque number"),
                NoticeField("cheque_date", "Cheque date"),
                NoticeField("cheque_amount", "Cheque amount"),
                NoticeField("drawee_bank", "Drawee bank"),
                NoticeField("dishonor_date", "Date of dishonor/return"),
                NoticeField("dishonor_reason", "Reason for dishonor (as stated by bank)"),
                NoticeField("payment_deadline_date", "Payment demanded within (date)"),
            ),
        ),
        NoticeTypeSpec(
            key="SPECIFIC_PERFORMANCE_NOTICE", title="Notice for Specific Performance", statute_reference=None,
            fields=(
                NoticeField("agreement_date", "Date of agreement"),
                NoticeField("agreement_description", "Brief description of the agreement"),
                NoticeField("performance_deadline_date", "Deadline demanded for performance"),
            ),
        ),
        NoticeTypeSpec(
            key="CONSUMER_PROTECTION_NOTICE", title="Consumer Protection Notice",
            statute_reference="Consumer Protection Act, 2019",
            fields=(
                NoticeField("product_or_service", "Product/service concerned"),
                NoticeField("purchase_date", "Date of purchase/service"),
                NoticeField("relief_sought", "Relief sought (refund/replacement/compensation)"),
            ),
        ),
        NoticeTypeSpec(
            key="SHOW_CAUSE_NOTICE", title="Show Cause Notice", statute_reference=None,
            fields=(
                NoticeField("response_deadline_date", "Deadline to respond"),
                NoticeField("consequence_summary", "Consequence of non-response", required=False),
            ),
        ),
        NoticeTypeSpec(
            key="DIVORCE_NOTICE", title="Divorce Notice", statute_reference=None,
            fields=(
                NoticeField("applicable_law", "Law the marriage was solemnized/governed under"),
                NoticeField("marriage_date", "Date of marriage"),
                NoticeField("marriage_place", "Place of marriage"),
            ),
        ),
        NoticeTypeSpec(
            key="RESTITUTION_OF_CONJUGAL_RIGHTS", title="Notice for Restitution of Conjugal Rights",
            statute_reference=None,
            fields=(
                NoticeField("marriage_date", "Date of marriage"),
                NoticeField("separation_date", "Date of separation"),
            ),
        ),
        NoticeTypeSpec(
            key="PARTITION_OF_PROPERTY", title="Legal Notice for Partition of Property", statute_reference=None,
            fields=(
                NoticeField("property_description", "Description of the property"),
                NoticeField("co_owners", "Other co-owners/parties"),
                NoticeField("share_claimed", "Share claimed"),
            ),
        ),
        NoticeTypeSpec(
            key="COPYRIGHT_INFRINGEMENT", title="Notice of Copyright Infringement",
            statute_reference="Copyright Act, 1957",
            fields=(
                NoticeField("work_description", "Description of the copyrighted work"),
                NoticeField("registration_number", "Copyright registration number (if any)", required=False),
            ),
        ),
        NoticeTypeSpec(
            key="TRADEMARK_INFRINGEMENT", title="Trademark Infringement Notice",
            statute_reference="Trade Marks Act, 1999",
            fields=(
                NoticeField("trademark_details", "Trademark details (word/logo, class)"),
                NoticeField("registration_number", "Trademark registration number (if any)", required=False),
            ),
        ),
        NoticeTypeSpec(
            key="RECOVERY_OF_DUES", title="Notice for Recovery of Dues / Money", statute_reference=None,
            fields=(
                NoticeField("principal_amount", "Principal amount due"),
                NoticeField("due_since_date", "Due since"),
                NoticeField("interest_claimed", "Interest claimed (if any)", required=False),
            ),
        ),
        NoticeTypeSpec(
            key="NOTICE_TO_INSURANCE_COMPANY", title="Notice to Insurance Company", statute_reference=None,
            fields=(
                NoticeField("policy_number", "Policy number"),
                NoticeField("policy_type", "Type of policy"),
                NoticeField("incident_date", "Date of incident/claim event"),
                NoticeField("claim_amount", "Claim amount"),
            ),
        ),
    ]
}