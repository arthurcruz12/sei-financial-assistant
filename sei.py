from dataclasses import dataclass, asdict
from typing import Dict


@dataclass
class FinancialProfile:
    income: float
    expenses: float
    emergency_fund: float
    target_months_emergency: int = 6


def validate_profile(profile: FinancialProfile) -> None:
    if profile.income < 0:
        raise ValueError("Income cannot be negative.")
    if profile.expenses < 0:
        raise ValueError("Expenses cannot be negative.")
    if profile.emergency_fund < 0:
        raise ValueError("Emergency fund cannot be negative.")
    if profile.target_months_emergency <= 0:
        raise ValueError("Target emergency months must be greater than zero.")


def calculate_savings(income: float, expenses: float) -> float:
    return income - expenses


def calculate_savings_rate(income: float, savings: float) -> float:
    if income == 0:
        return 0.0
    return (savings / income) * 100


def classify_financial_health(savings_rate: float) -> str:
    if savings_rate >= 20:
        return "Healthy"
    if savings_rate >= 10:
        return "Moderate"
    if savings_rate >= 0:
        return "Risky"
    return "Critical"


def calculate_emergency_target(expenses: float, target_months: int) -> float:
    return expenses * target_months


def estimate_months_to_emergency_goal(
    emergency_fund: float,
    emergency_target: float,
    monthly_savings: float,
) -> float | None:
    if emergency_fund >= emergency_target:
        return 0.0
    if monthly_savings <= 0:
        return None
    missing_amount = emergency_target - emergency_fund
    return missing_amount / monthly_savings


def generate_recommendation(
    profile_status: str,
    monthly_savings: float,
    savings_rate: float,
    months_to_goal: float | None,
) -> str:
    if profile_status == "Healthy":
        if months_to_goal == 0:
            return (
                "Your financial profile is strong. You already have your emergency fund "
                "covered. Consider diversifying into long-term investments."
            )
        return (
            "You have a healthy savings rate. Continue saving consistently and consider "
            "investing part of your surplus after strengthening your emergency reserve."
        )

    if profile_status == "Moderate":
        if months_to_goal is None:
            return (
                "Your finances are relatively stable, but your current savings are not enough "
                "to build your emergency fund. Reduce discretionary expenses and increase savings."
            )
        return (
            "Your financial situation is stable, but there is room for improvement. Focus on "
            "raising your savings rate and accelerating your emergency fund."
        )

    if profile_status == "Risky":
        return (
            "Your savings rate is low. Review monthly expenses, cut non-essential costs, "
            "and prioritize building an emergency reserve before taking investment risks."
        )

    return (
        "Your expenses are above your income. Immediate financial adjustment is needed: "
        "reduce expenses, increase income if possible, and avoid new debt."
    )


def analyze_financial_profile(profile: FinancialProfile) -> Dict:
    validate_profile(profile)

    monthly_savings = calculate_savings(profile.income, profile.expenses)
    savings_rate = calculate_savings_rate(profile.income, monthly_savings)
    status = classify_financial_health(savings_rate)

    emergency_target = calculate_emergency_target(
        profile.expenses,
        profile.target_months_emergency,
    )

    months_to_goal = estimate_months_to_emergency_goal(
        emergency_fund=profile.emergency_fund,
        emergency_target=emergency_target,
        monthly_savings=monthly_savings,
    )

    recommendation = generate_recommendation(
        profile_status=status,
        monthly_savings=monthly_savings,
        savings_rate=savings_rate,
        months_to_goal=months_to_goal,
    )

    result = {
        "input": asdict(profile),
        "monthly_savings": round(monthly_savings, 2),
        "savings_rate_percent": round(savings_rate, 2),
        "financial_status": status,
        "emergency_fund_target": round(emergency_target, 2),
        "current_emergency_fund": round(profile.emergency_fund, 2),
        "months_to_emergency_goal": (
            None if months_to_goal is None else round(months_to_goal, 1)
        ),
        "recommendation": recommendation,
    }

    return result


def print_report(result: Dict) -> None:
    print("\n=== SEI Financial Analysis Report ===")
    print(f"Income: €{result['input']['income']:.2f}")
    print(f"Expenses: €{result['input']['expenses']:.2f}")
    print(f"Emergency Fund: €{result['input']['emergency_fund']:.2f}")
    print(f"Monthly Savings: €{result['monthly_savings']:.2f}")
    print(f"Savings Rate: {result['savings_rate_percent']:.2f}%")
    print(f"Financial Status: {result['financial_status']}")
    print(f"Emergency Fund Target: €{result['emergency_fund_target']:.2f}")

    months = result["months_to_emergency_goal"]
    if months is None:
        print("Months to Emergency Goal: Not achievable with current savings level")
    else:
        print(f"Months to Emergency Goal: {months}")

    print(f"Recommendation: {result['recommendation']}")
    print("=====================================\n")


if __name__ == "__main__":
    sample_profile = FinancialProfile(
        income=2000.0,
        expenses=1500.0,
        emergency_fund=1000.0,
        target_months_emergency=6,
    )

    analysis = analyze_financial_profile(sample_profile)
    print_report(analysis)
