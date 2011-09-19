{#<%@ page language="java" contentType="text/html; charset=utf-8"#}
{#	pageEncoding="utf-8" errorPage="/error.jsp"%>#}
{##}
{#<jsp:useBean id="transactionDetails" scope="request" type="com.creditguard.common.transactions.TransactionDetails" />#}
{#<%@ include file="/merchantPages/WebSources/includes/main.jsp" %>#}
{#<script src="merchantPages/WebSources/js/EN.js"></script>#}
{#<script src="merchantPages/WebSources/js/main.js"></script>#}

{% extends "wb_base_site.html" %}
{% load i18n %}

{% block extrastyle %}
    {{ block.super }}
    <style type="text/css">
        #content-container{min-height: 0;}
        
        .td_style_fieldName {
            font-weight: bold;
            font-size: 13px;
            width: 150px;
            height: 50px;
        }

        input {
            height: 25px;
        }

        #cardNumber, #personalId {
            width: 210px;
        }

        #cvv {
            width: 50px;
        }

        #CVVhelp {
            width: 18px;
            height: 18px;
            background: url("/static/images/wb_site/question_mark.png") left 0 no-repeat;
            cursor:pointer;
            display: inline-block;
            position: relative;
            top: 2px;
            left: 4px;
        }

        #wb_lock {
            width: 33px;
            height: 52px;
            background: url("/static/images/wb_site/lock.png") left 0 no-repeat;
            display: inline-block;
            position: relative;
            top: 22px;
        }

        #wb_content_footer {
            height: 40px;
            border-top: 1px solid #BCBCBC;
            padding-top: 20px;
            margin-top: 40px;
            position: relative;
        }

        #wb_cg_logo {
            width: 164px;
            height: 44px;
            background: url("/static/images/wb_site/credit-guard.png") left 0 no-repeat;
            float: left;
        }

        #wb_cards {
            width: 218px;
            height: 34px;
            background: url("/static/images/wb_site/card_types.png") left 0 no-repeat;
            float: left;
            margin-left: 55px;
        }

        #submitBtn {
            position: absolute;
            bottom: 0;
            right: 0;
        }

        #site-footer {
            position: relative;
            padding-top: 20px;
        }

        #wb_ssl {
            width: 117px;
            height: 58px;
            background: url("/static/images/wb_site/ssl.png") left 0 no-repeat;
            display: inline-block;
        }

        #wb_ssl_text {
            position: absolute;
            top: 20px;
            display: inline-block;
            margin-left: 20px;
            color: white;
        }
    </style>

{% endblock %}

{% block top_left %}
    {% trans "Enter Payment Method" %}
{% endblock %}

{% block top_right %}
    {% trans "Secured Payment" %}
    <div id="wb_lock"></div>
{% endblock %}

{% block content %}
    <form id="creditForm" onsubmit="return formValidator(0);" method="POST" action="ProcessCreditCard">
        <input type="hidden" name="txId" value="<%=mpiTxnId%>"/>
        <input type="hidden" name="lang" value="EN"/>
        <input type="hidden" name="track2" value="" autocomplete="off"/>
        <input type="hidden" name="last4d" value="" autocomplete="off"/>
        <input type="hidden" name="cavv" value="" autocomplete="off"/>
        <input type="hidden" name="eci" value="" autocomplete="off"/>
        <input type="hidden" name="transactionCode" value="Phone" autocomplete="off"/>
        <table class="data_tbl">
            <tr>
                <td class="td_style_fieldName">{% trans "Card Number" %}</td>
                <td><input type="text" id="cardNumber" name="cardNumber" maxlength="19" autocomplete="off"/></td>
                <td class="td_style_fieldName"></td>
            </tr>
            <tr>
                <td class="td_style_fieldName">{% trans "Expiration Date" %}</td>
                <td>
                    <select id="expYear" name="expYear">
                        <%=expYear%>
                    </select>
                    -
                    <select id="expMonth" name="expMonth">
                        <option value="01">01</option>
                        <option value="02">02</option>
                        <option value="03">03</option>
                        <option value="04">04</option>
                        <option value="05">05</option>
                        <option value="06">06</option>
                        <option value="07">07</option>
                        <option value="08">08</option>
                        <option value="09">09</option>
                        <option value="10">10</option>
                        <option value="11">11</option>
                        <option value="12">12</option>
                    </select>
                </td>
                <td class="td_style_fieldName"></td>
            </tr>
            <tr>
                <td class="td_style_fieldName">CVV</td>
                <td><input type="text" name="cvv" id="cvv" maxlength="4" autocomplete="off"/>
                    <div id="CVVhelp" onmouseover="showHideCVVhelp();" onmouseout="showHideCVVhelp();"></div>
                </td>
                <td class="td_style_fieldName"></td>
            </tr>
            <tr>
                <td class="td_style_fieldName">{% trans "Card Owner ID" %}</td>
                <td><input type="text" id="personalId" name="personalId" maxlength="9" autocomplete="off"/></td>
                <td class="td_style_fieldName"></td>
            </tr>
        </table>
        <div id="wb_content_footer">
            <div id="wb_cg_logo"></div>
            <div id="wb_cards"></div>
            <input type="submit" id="submitBtn" value="{% trans "Finish" %}"/>
        </div>
    </form>

{% endblock %}

{% block post_content %}
{% endblock %}

{% block footer %}
    <div id="wb_ssl"></div>
    <div id="wb_ssl_text">
        {% trans "In this page you can pay for the order you placed on" %} WAYbetter.com
        <br/>
        {% trans "The payment process is fully secure and complies with the highest standards of data protection" %}.
        <br/>
        {% trans "Please insert your credit card details as required above" %}.
        <br/>
        {% trans "Payment for the order will only be auctioned after you click on the 'Next' button at the bottom on the screen" %}.
    </div>
{% endblock %}

