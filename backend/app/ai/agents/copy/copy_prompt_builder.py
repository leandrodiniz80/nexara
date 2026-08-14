from app.ai.agents.copy.copy_context_builder import CopyContext


class CopyPromptBuilder:
    """Assembles the prompt CopyAgent sends to the provider — section by section, from
    a CopyContext. No prompt text lives in CopyAgent itself; every fixed phrase used to
    label/frame a section lives here, and every variable piece comes from CopyContext.
    """

    def build(self, context: CopyContext) -> str:
        sections = [
            self._context_section(context),
            self._objective_section(context),
            self._restrictions_section(),
            self._company_section(context),
            self._prospect_section(context),
            self._mission_section(context),
            self._recommendations_section(context),
            self._output_format_section(),
        ]
        return "\n\n".join(section for section in sections if section)

    def _context_section(self, context: CopyContext) -> str:
        lines = [
            "## Context",
            f"Asset type: {context.asset_type.value}",
        ]
        if context.channel:
            lines.append(f"Channel: {context.channel.value}")
        if context.tone:
            lines.append(f"Tone: {context.tone}")
        if context.communication_style:
            lines.append(f"Communication style: {context.communication_style}")
        lines.append(f"Language: {context.language}")
        return "\n".join(lines)

    def _objective_section(self, context: CopyContext) -> str:
        objective = context.variables.get("objective")
        if not objective and context.mission is not None:
            objective = context.mission.objective
        if not objective:
            return ""
        return f"## Objective\n{objective}"

    def _restrictions_section(self) -> str:
        return (
            "## Restrictions\n"
            "Do not invent facts about the company or prospect beyond what is given "
            "below. Do not promise pricing, discounts, or contractual terms. Do not "
            "use aggressive or misleading language. Respect the requested tone and "
            "asset type."
        )

    def _company_section(self, context: CopyContext) -> str:
        company = context.company
        if company is None:
            return ""
        name = company.trade_name or company.legal_name
        lines = ["## Company", f"Name: {name}"]
        if company.segment:
            lines.append(f"Segment: {company.segment}")
        if company.city:
            location = company.city
            if company.state:
                location = f"{location}/{company.state}"
            lines.append(f"Location: {location}")
        return "\n".join(lines)

    def _prospect_section(self, context: CopyContext) -> str:
        lines = ["## Prospect"]
        contact_name = context.variables.get("contact_name")
        if contact_name:
            lines.append(f"Contact: {contact_name}")
        if context.prospect is not None:
            lines.append(f"Stage: {context.prospect.current_stage.value}")
            lines.append(f"Temperature: {context.prospect.temperature.value}")
        if len(lines) == 1:
            return ""
        return "\n".join(lines)

    def _mission_section(self, context: CopyContext) -> str:
        mission = context.mission
        if mission is None:
            return ""
        lines = ["## Mission", f"Name: {mission.name}"]
        if mission.target_segment:
            lines.append(f"Target segment: {mission.target_segment}")
        if mission.target_city:
            lines.append(f"Target city: {mission.target_city}")
        return "\n".join(lines)

    def _recommendations_section(self, context: CopyContext) -> str:
        lines = ["## Recommendations"]
        if context.commercial_score is not None:
            lines.append(f"Commercial score: {context.commercial_score}")
        if context.commercial_profile:
            lines.append(f"Commercial profile: {context.commercial_profile}")
        for recommendation in context.recommendations:
            lines.append(f"- {recommendation}")
        if len(lines) == 1:
            return ""
        return "\n".join(lines)

    def _output_format_section(self) -> str:
        return (
            "## Output Format\n"
            "Respond with a single JSON object and nothing else, in the shape:\n"
            '{"title": "<string or null>", "content": "<string>", '
            '"metadata": {"<optional extra key>": "<value>"}}\n'
            "`title` must be null for channels that have no subject line (e.g. WhatsApp)."
        )
