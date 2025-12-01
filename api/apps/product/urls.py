from django.urls import path

from .views import (ProductListAPIView, ProductRetrieveAPIView, 
                    ProductCategoryListAPIView, ProductTagListAPIView, 
                    ProductFormulaRetrieveAPIView, ProductFormulaCalculateAPIView,
                    ProductFullAPIView)


urlpatterns = [
    path('', ProductListAPIView.as_view(), name='products_list'),
    path('<int:id>/', ProductRetrieveAPIView.as_view(), name='product_retrieve'),
    path('categories/', ProductCategoryListAPIView.as_view(), name='product_categories_list'),
    path('tags/', ProductTagListAPIView.as_view(), name='product_tags_list'),
    path('formulas/<int:id>/', ProductFormulaRetrieveAPIView.as_view(), name='product_formulas_list'),
    path('formulas/calculate/', ProductFormulaCalculateAPIView.as_view(), name='product_formula_calculate'),
    path('full/', ProductFullAPIView.as_view(), name='products_full'),
]
