from abc import ABC, abstractmethod

class AnalysisStrategy(ABC):
    """解析アプローチを切り替える抽象ベース戦略クラス"""
    @abstractmethod
    def adjust_prompt(self, base_prompt: str) -> str:
        pass

class ScanModeStrategy(AnalysisStrategy):
    """スキャンモード：10秒で全体を把握するための超高速・要約特化戦略"""
    def adjust_prompt(self, base_prompt: str) -> str:
        return base_prompt + "\n【重要指示: スキャンモード】重箱の隅は突つかず、全体構造、主要な結論、および合計金額などの決定的な数字のみを最優先で10秒で把握できるよう簡潔に要約・抽出してください。"

class DeepDigModeStrategy(AnalysisStrategy):
    """ディープディグモード：矛盾、契約リスク、不整合を炙り出すための深層解析戦略"""
    def adjust_prompt(self, base_prompt: str) -> str:
        return base_prompt + "\n【重要指示: ディープディグモード】ドキュメント内の論理的矛盾、不審な条項、他社比較における潜在的なリーガルリスクやペインポイントを徹底的に炙り出して構造化データ内に反映してください。"

class StrategyProvider:
    """要求されたモードに応じて適切な戦略オブジェクトを返すFactory兼任"""
    @staticmethod
    def get_strategy(mode: str) -> AnalysisStrategy:
        if mode == "deep":
            return DeepDigModeStrategy()
        return ScanModeStrategy() # デフォルトは安全側に倒してスキャンモード