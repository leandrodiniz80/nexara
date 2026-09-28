import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse } from "@/lib/api/types";

export interface ConsoleMoney {
  todayPossible: number;
  gap: number;
  atRisk: number;
}

export interface ConsoleTopPriority {
  leadId: string;
  name: string;
  value: number;
  action: string | null;
  urgency: string;
  reason: string | null;
}

export interface SystemConsole {
  status: string;
  message: string;
  money: ConsoleMoney;
  focus: string;
  mainAction: string;
  requiredActions: number;
  executionBlocked: boolean;
  topPriorities: ConsoleTopPriority[];
  executionPlan: string[];
  nextSteps: string[];
  consistencyWarning: boolean;
}

interface ConsoleMoneyDto {
  today_possible: number;
  gap: number;
  at_risk: number;
}

interface ConsoleTopPriorityDto {
  lead_id: string;
  name: string;
  value: number;
  action: string | null;
  urgency: string;
  reason: string | null;
}

interface SystemConsoleDto {
  status: string;
  message: string;
  money: ConsoleMoneyDto;
  focus: string;
  main_action: string;
  required_actions: number;
  execution_blocked: boolean;
  top_priorities: ConsoleTopPriorityDto[];
  execution_plan: string[];
  next_steps: string[];
  consistency_warning: boolean;
}

/** GET /api/v1/system/console — Nexara Live Console: the one-glance,
 * one-number, one-action view a non-technical owner opens every morning. */
export async function getConsole(): Promise<SystemConsole> {
  try {
    const { data } = await apiClient.get<ApiResponse<SystemConsoleDto>>("/system/console");
    if (!data.data) {
      throw new Error("Console request succeeded but returned no data");
    }
    const dto = data.data;
    return {
      status: dto.status,
      message: dto.message,
      money: {
        todayPossible: dto.money.today_possible,
        gap: dto.money.gap,
        atRisk: dto.money.at_risk,
      },
      focus: dto.focus,
      mainAction: dto.main_action,
      requiredActions: dto.required_actions,
      executionBlocked: dto.execution_blocked,
      topPriorities: dto.top_priorities.map((entry) => ({
        leadId: entry.lead_id,
        name: entry.name,
        value: entry.value,
        action: entry.action,
        urgency: entry.urgency,
        reason: entry.reason,
      })),
      executionPlan: dto.execution_plan,
      nextSteps: dto.next_steps,
      consistencyWarning: dto.consistency_warning,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface ExecuteActionResult {
  executed: boolean;
  action: string | null;
  messageGenerated: string | null;
  expectedRevenueImpact: number;
}

interface SystemExecuteActionDto {
  executed: boolean;
  action: string | null;
  message_generated: string | null;
  expected_revenue_impact: number;
}

/** POST /api/v1/system/execute-action — executes whatever action the
 * system already recommends for this lead (its own next_best_action_type),
 * so the console's "Executar agora" button never has to name one itself. */
export async function executeSystemAction(leadId: string): Promise<ExecuteActionResult> {
  try {
    const { data } = await apiClient.post<ApiResponse<SystemExecuteActionDto>>(
      "/system/execute-action",
      { lead_id: leadId }
    );
    if (!data.data) {
      throw new Error("Execute-action request succeeded but returned no data");
    }
    return {
      executed: data.data.executed,
      action: data.data.action,
      messageGenerated: data.data.message_generated,
      expectedRevenueImpact: data.data.expected_revenue_impact,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface DemoSeedResult {
  created: number;
  ready: boolean;
  autoOpen: string;
  expectedResult: string;
}

interface SystemDemoSeedDto {
  created: number;
  ready: boolean;
  auto_open: string;
  expected_result: string;
}

/** POST /api/v1/system/demo-seed — seeds a realistic demo pipeline (10
 * leads across new/contacted/lost) for sales demos and first-access. */
export async function seedDemoData(): Promise<DemoSeedResult> {
  try {
    const { data } = await apiClient.post<ApiResponse<SystemDemoSeedDto>>("/system/demo-seed");
    if (!data.data) {
      throw new Error("Demo-seed request succeeded but returned no data");
    }
    return {
      created: data.data.created,
      ready: data.data.ready,
      autoOpen: data.data.auto_open,
      expectedResult: data.data.expected_result,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}
